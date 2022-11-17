#
# Copyright (c) 2021 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import time
import oslo_messaging
import logging
from notificationclientsdk.model.dto.rpc_endpoint import RpcEndpointInfo
from notificationclientsdk.common.helpers import constants
from notificationclientsdk.common.helpers import log_helper
from notificationclientsdk.client.locationservice import LocationServiceClient
from notificationclientsdk.client.notificationservice \
    import NotificationServiceClient

LOG = logging.getLogger(__name__)
log_helper.config_logger(LOG)


class BrokerConnectionManager:

    def __init__(self, broker_location_handler, notification_handler,
                 broker_connection_contexts):
        '''
        broker_watchers: {
            "<broker name1>": {
                "broker_client": client1,
                "subscribed_resource_list": ['PTP', ...]
            },
            {...}
            ...
        }
        '''
        self.shared_broker_context = broker_connection_contexts
        self.registration_endpoint = RpcEndpointInfo(
            self.shared_broker_context['REGISTRATION_TRANSPORT_ENDPOINT'])
        self.broker_watchers = {}
        self.location_watcher = LocationServiceClient(
            self.registration_endpoint.TransportEndpoint)
        self.__broker_location_handler = broker_location_handler
        self.__notification_handler = notification_handler

    def __del__(self):
        if self.location_watcher:
            self.location_watcher.cleanup()
            del self.location_watcher
            self.location_watcher = None

    def start(self):
        self.__start_watch_all_nodes()

    def stop(self):
        self.__stop_watch_all_nodes()

    def __validate(self, brokerstate):
        valid = brokerstate.BrokerName or brokerstate.BrokerIP
        return valid

    def start_watching_broker(self, brokerstate):
        try:
            if not self.__validate(brokerstate):
                return False

            broker_name = brokerstate.BrokerName

            # must make sure the location is updated/watched:
            # 1, check and start location watcher
            if not self.location_watcher.is_listening_on_location(broker_name):
                # start watching on the location announcement
                self.location_watcher.add_location_listener(
                    broker_name,
                    location_handler=self.__broker_location_handler)
                LOG.debug("Start watching location announcement of "
                          "notificationservice@{0}".format(broker_name))
                # try to update location by query
                try:
                    location_info = self.location_watcher.query_location(
                        broker_name, timeout=5, retry=2)
                    LOG.debug("Pulled location info@{0}:{1}".format(
                        broker_name, location_info))
                    if location_info:
                        podip = location_info.get("PodIP", None)
                        resourcetypes = location_info.get("ResourceTypes",
                                                          None)
                        brokerstate.update_broker_ip(podip)
                        brokerstate.update_resources(resourcetypes)
                    else:
                        return False
                except Exception as ex:
                    LOG.warning("Failed to update location of node:{0} "
                                "due to: {1}".format(broker_name, str(ex)))
                    raise ex

            # 2, create broker connection
            broker_watcher = self.broker_watchers.get(broker_name, {})
            broker_client = broker_watcher.get("broker_client", None)
            if not broker_client:
                LOG.debug("Start watching notifications from "
                          "notificationservice@{0}".format(broker_name))
                broker_client = self.__create_client(broker_name,
                                                     brokerstate.BrokerIP)
                broker_watcher["broker_client"] = broker_client
                self.broker_watchers[broker_name] = broker_watcher

            # 3, update watching resources
            result = self.__update_watching_resources(broker_watcher,
                                                      broker_client,
                                                      brokerstate)
            return result
        except Exception as ex:
            LOG.warning("failed to start watching:{0},{1}".format(
                brokerstate, str(ex)))
            return False

    def __stop_watching_broker_resource(self, broker_client, broker_name,
                                        resource_type):
        try:
            if broker_client.is_listening_on_resource(resource_type):
                broker_client.remove_resource_status_listener(resource_type)
            return True
        except Exception as ex:
            LOG.warning("failed to stop watching resource:{0}@{1},{2}".format(
                broker_name, resource_type, str(ex)))
            return False

    def __start_watching_broker_resource(self, broker_client, broker_name,
                                         resource_type):
        try:
            if not broker_client.is_listening_on_resource(resource_type):
                broker_client.add_resource_status_listener(
                    resource_type, status_handler=self.__notification_handler)
                LOG.debug("Start watching {0}@{1}".format(resource_type,
                                                          broker_name))

            return True
        except Exception as ex:
            LOG.warning("failed to start watching resource:{0}@{1},{2}".format(
                resource_type, broker_name, str(ex)))
            return False

    def stop_watching_broker(self, broker_name):
        try:
            # 1, stop listening to broker's location announcement
            if self.location_watcher.is_listening_on_location(broker_name):
                self.location_watcher.remove_location_listener(broker_name)
                LOG.debug("Stop watching location announcement for broker@{0}"
                          "".format(broker_name))

            # 2, remove broker client
            broker_watcher = self.broker_watchers.get(broker_name, {})
            broker_client = broker_watcher.get("broker_client", None)
            if broker_client:
                broker_client.cleanup()
                del broker_client
                broker_client = None
                self.broker_watchers.pop(broker_name, None)
                LOG.debug("Stop watching notificationservice@{0}".format(
                    broker_name))

            return True
        except Exception as ex:
            LOG.warning("failed to start watching:{0},{1}".format(
                broker_name, str(ex)))
            return False

    def restart_watching_broker(self, brokerstate):
        try:
            broker_name = brokerstate.BrokerName
            LOG.debug("Try to restart watching notificationservice@{0}".format(
                broker_name))
            broker_watcher = self.broker_watchers.get(broker_name, {})
            broker_client = broker_watcher.get("broker_client", None)
            if broker_client:
                broker_client.cleanup()
                del broker_client
                broker_client = None
                self.broker_watchers.pop(broker_name, None)
            return self.start_watching_broker(brokerstate)
        except Exception as ex:
            LOG.warning("failed to restart watching:{0},{1}".format(
                brokerstate, str(ex)))
            return False

    def update_watching_resources(self, brokerstate):
        try:
            broker_watcher = self.broker_watchers.get(brokerstate.BrokerName,
                                                      {})
            broker_client = broker_watcher.get("broker_client", None)
            if broker_client:
                result = self.__update_watching_resources(broker_watcher,
                                                          broker_client,
                                                          brokerstate)
                return result
            return False
        except Exception as ex:
            LOG.warning("failed to start watching:{0},{1}".format(
                brokerstate, str(ex)))
            return False

    def __update_watching_resources(self, broker_watcher, broker_client,
                                    brokerstate):
        try:
            result = True
            # 1, filter out those unsubscribed resources
            subscribed_resource_list = broker_watcher.get(
                "subscribed_resource_list", [])
            if subscribed_resource_list != brokerstate.ResourceTypesSubscribed:
                # stop watching those uninterested
                for resource_type in subscribed_resource_list:
                    if resource_type not in \
                            brokerstate.ResourceTypesSubscribed:
                        result = self.__stop_watching_broker_resource(
                            broker_client, brokerstate.BrokerName,
                            resource_type)

            # 2, update the list
            subscribed_resource_list = brokerstate.ResourceTypesSubscribed
            broker_watcher["subscribed_resource_list"] = \
                subscribed_resource_list

            # 3, start watching the subscribed resources
            for resource_type in subscribed_resource_list:
                result = self.__start_watching_broker_resource(
                    broker_client, brokerstate.BrokerName, resource_type) and \
                        result
            return result
        except Exception as ex:
            LOG.warning("failed to update resources:{0},{1}".format(
                brokerstate, str(ex)))
            return False

    def is_watching_broker(self, broker_name):
        broker_watcher = self.broker_watchers.get(broker_name, {})
        broker_client = broker_watcher.get("broker_client", None)
        return broker_client is not None

    def is_watching_resource(self, broker_name, resource_type):
        broker_watcher = self.broker_watchers.get(broker_name, {})
        broker_client = broker_watcher.get("broker_client", None)
        return broker_client.is_listening_on_resource(
            resource_type) if broker_client else False

    def __create_client(self, broker_name, broker_pod_ip):
        if broker_name == constants.WILDCARD_ALL_NODES:
            # special case: if monitor all node, then use the same broker as
            # locationservice
            return self.location_watcher
        broker_host = "[{0}]".format(broker_pod_ip)
        broker_transport_endpoint = "rabbit://{0}:{1}@{2}:{3}".format(
            self.shared_broker_context['NOTIFICATION_BROKER_USER'],
            self.shared_broker_context['NOTIFICATION_BROKER_PASS'],
            broker_host,
            self.shared_broker_context['NOTIFICATION_BROKER_PORT'])
        return NotificationServiceClient(broker_name,
                                         broker_transport_endpoint,
                                         broker_pod_ip)

    def __start_watch_all_nodes(self, retry_interval=5):
        try:
            LOG.debug("Start watching location announcement of "
                      "notificationservice@{0}".format(
                        constants.WILDCARD_ALL_NODES))
            while not self.location_watcher.is_listening_on_location(
                    constants.WILDCARD_ALL_NODES):
                # start watching on the location announcement
                self.location_watcher.add_location_listener(
                    constants.WILDCARD_ALL_NODES,
                    location_handler=self.__broker_location_handler)
                if not self.location_watcher.is_listening_on_location(
                        constants.WILDCARD_ALL_NODES):
                    # retry later and forever
                    LOG.debug(
                        "Retry indefinitely to start listening to {0}..."
                        .format(constants.WILDCARD_ALL_NODES))
                    time.sleep(retry_interval)

            LOG.debug(
                "Trigger the location announcement of notificationservice@{0}"
                .format(constants.WILDCARD_ALL_NODES))
            self.location_watcher.trigger_location_annoucement(timeout=20,
                                                               retry=10)
        except Exception as ex:
            LOG.warning("exception: {0}".format(str(ex)))
            pass
        finally:
            pass
        return

    def __stop_watch_all_nodes(self):
        pass

    def __syncup_data_by_resourcetype(self, broker_client, broker_name,
                                      resource_type):
        # check to sync up resource status on a node
        LOG.debug("try to sync up data for {0}@{1}".format(
            resource_type, broker_name))
        try:
            if broker_name == constants.WILDCARD_ALL_NODES:
                self.location_watcher.trigger_publishing_status(
                    resource_type, timeout=5, retry=10)
                return True

            # 1, query resource status
            broker_client = self.broker_watchers.get(broker_name, None)
            if not broker_client:
                raise Exception("watcher is not ready for broker: {0}".format(
                    broker_name))
            resource_status = broker_client.query_resource_status(
                resource_type, timeout=5, retry=10)

            # 2, deliver resource by comparing LastDelivery time with
            #    EventTimestamp
            # 3, update the LastDelivery with EventTimestamp
            self.__notification_handler.handle(resource_status)
        except oslo_messaging.exceptions.MessagingTimeout as ex:
            LOG.warning("Fail to sync up data {0}@{1}, due to {2}".format(
                resource_type, broker_name, str(ex)))
            return False
        except Exception as ex:
            LOG.warning("Fail to sync up data {0}@{1}, due to {2}".format(
                resource_type, broker_name, str(ex)))
            raise ex
        finally:
            pass
        return True

    def syncup_broker_data(self, brokerstate):
        aggregated_result = True
        broker_name = brokerstate.BrokerName
        try:
            broker_watcher = self.broker_watchers.get(broker_name, {})
            broker_client = broker_watcher.get("broker_client", None)
            subscribed_resource_list = broker_watcher.get(
                "subscribed_resource_list", [])
            for resource_type in subscribed_resource_list:
                if not brokerstate.is_data_syncup(resource_type):
                    continue
                result = self.__syncup_data_by_resourcetype(
                    broker_client, broker_name, resource_type)
                if result:
                    brokerstate.ack_data_syncup(resource_type)
                aggregated_result = aggregated_result and result
            return aggregated_result
        except Exception as ex:
            LOG.warning("failed to sync up data for resources:{0},{1}".format(
                broker_name, str(ex)))
            return False
