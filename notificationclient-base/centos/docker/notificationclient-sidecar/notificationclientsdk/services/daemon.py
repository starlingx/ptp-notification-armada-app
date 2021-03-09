#
# Copyright (c) 2021 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import os
import json
import time
import oslo_messaging
from oslo_config import cfg
import logging

import multiprocessing as mp
import threading
import sys
if sys.version > '3':
    import queue as Queue
else:
    import Queue

from notificationclientsdk.common.helpers import subscription_helper
from notificationclientsdk.common.helpers import rpc_helper, hostfile_helper
from notificationclientsdk.common.helpers.nodeinfo_helper import NodeInfoHelper

from notificationclientsdk.model.dto.rpc_endpoint import RpcEndpointInfo
from notificationclientsdk.model.dto.subscription import SubscriptionInfo
from notificationclientsdk.model.dto.resourcetype import ResourceType
from notificationclientsdk.model.dto.location import LocationInfo

from notificationclientsdk.repository.dbcontext import DbContext
from notificationclientsdk.repository.subscription_repo import SubscriptionRepo

from notificationclientsdk.model.orm.node import NodeInfo as NodeInfoOrm

from notificationclientsdk.repository.node_repo import NodeRepo

from notificationclientsdk.client.locationservice import LocationServiceClient
from notificationclientsdk.client.notificationservice import NotificationServiceClient
from notificationclientsdk.client.notificationservice import NotificationHandlerBase

from notificationclientsdk.client.locationservice import LocationHandlerDefault

LOG = logging.getLogger(__name__)

from notificationclientsdk.common.helpers import log_helper
log_helper.config_logger(LOG)

'''Entry point of Default Process Worker'''
def ProcessWorkerDefault(event, subscription_event, daemon_context):
    worker = NotificationWorker(event, subscription_event, daemon_context)
    worker.run()
    return


class NotificationWorker:

    class NotificationWatcher(NotificationHandlerBase):
        def __init__(self, notification_watcher):
            self.notification_watcher = notification_watcher
            super(NotificationWorker.NotificationWatcher, self).__init__()

        def handle(self, notification_info):
            LOG.debug("Received notification:{0}".format(notification_info))
            result = self.notification_watcher.handle_notification_delivery(notification_info)
            return result

    class NodeInfoWatcher(LocationHandlerDefault):
        def __init__(self, notification_watcher):
            self.notification_watcher = notification_watcher
            super(NotificationWorker.NodeInfoWatcher, self).__init__()

        def handle(self, location_info):
            LOG.debug("Received location info:{0}".format(location_info))
            return self.notification_watcher.produce_location_event(location_info)

    def __init__(
        self, event, subscription_event, daemon_context):

        self.daemon_context = daemon_context
        self.residing_node_name = daemon_context['THIS_NODE_NAME']
        NodeInfoHelper.set_residing_node(self.residing_node_name)

        self.sqlalchemy_conf = json.loads(daemon_context['SQLALCHEMY_CONF_JSON'])
        DbContext.init_dbcontext(self.sqlalchemy_conf)
        self.event = event
        self.subscription_event = subscription_event

        self.registration_endpoint = RpcEndpointInfo(daemon_context['REGISTRATION_TRANSPORT_ENDPOINT'])
        self.locationservice_client = LocationServiceClient(self.registration_endpoint.TransportEndpoint)
        # dict,key: node name, value , notificationservice client
        self.notificationservice_clients = {}

        # Watcher callback
        self.__NotificationWatcher = NotificationWorker.NotificationWatcher(self)
        self.__NodeInfoWatcher = NotificationWorker.NodeInfoWatcher(self)

        self.__init_node_resources_map()
        self.__init_node_info_channel()
        self.__init_location_channel()
        self.__init_notification_channel()
        self.__init_node_sync_channel()

    def __init_node_resources_map(self):
        self.node_resources_map = {}
        self.node_resources_iteration = 0
        self.__node_resources_event = mp.Event()

    def __init_node_info_channel(self):
        self.__node_info_event = mp.Event()

    def __init_location_channel(self):
        self.location_event = mp.Event()
        self.location_lock = threading.Lock()
        # map index by node name
        # only cache the latest loation info
        self.location_channel = {}
        self.location_keys_q = Queue.Queue()

    def __init_notification_channel(self):
        self.notification_lock = threading.Lock()
        self.notification_stat = {}

    def __init_node_sync_channel(self):
        self.__node_sync_event = mp.Event()
        self.__node_sync_q = Queue.Queue()
        # initial to be set
        self.__node_sync_event.set()

    def __del__(self):
        del self.locationservice_client

    def signal_location_event(self):
        self.location_event.set()

    def signal_subscription_event(self):
        self.subscription_event.set()

    def signal_node_sync_event(self):
        self.__node_sync_event.set()

    def signal_nodeinfo_event(self):
        self.__node_info_event.set()

    def signal_node_resources_event(self):
        self.__node_resources_event.set()

    def signal_events(self):
        self.event.set()

    def produce_location_event(self, location_info):
        node_name = location_info.get('NodeName', None)
        podip = location_info.get("PodIP", None)
        if not node_name or not podip:
            LOG.warning("Missing PodIP inside location info:{0}".format(location_info))
            return False

        result = True
        timestamp = location_info.get('Timestamp', 0)
        # acquire lock to sync threads which invoke this method
        self.location_lock.acquire()
        try:
            current = self.location_channel.get(node_name, {})
            if current.get('Timestamp', 0) < timestamp:
                if current.get('PodIP', None) != podip:
                    # update /etc/hosts must happen in threads to avoid blocking by the main thread
                    NOTIFICATIONSERVICE_HOSTNAME = 'notificationservice-{0}'
                    hostfile_helper.update_host(
                        NOTIFICATIONSERVICE_HOSTNAME.format(node_name), podip)
                    LOG.debug("Updated location with IP:{0}".format(podip))

                # replace the location_info
                self.location_channel[node_name] = location_info
                self.location_keys_q.put(node_name)
                # notify the consumer to process the update
                self.signal_location_event()
                self.signal_events()
                result = True
        except Exception as ex:
            LOG.warning("failed to produce location event:{0}".format(str(ex)))
            result = False
        finally:
            # release lock
            self.location_lock.release()

        return result

    def consume_location_event(self):
        LOG.debug("Start consuming location event")
        need_to_sync_node = False
        node_changed = False
        node_resource_updated = False
        nodeinfo_repo = NodeRepo(autocommit=True)

        while not self.location_keys_q.empty():
            node_name = self.location_keys_q.get(False)
            location_info = self.location_channel.get(node_name, None)
            if not location_info:
                LOG.warning("consume location@{0} without location info".format(node_name))
                continue

            LOG.debug("process location event@{0}:{1}".format(node_name, location_info))

            location_info2 = LocationInfo(**location_info)

            entry = nodeinfo_repo.get_one(NodeName=location_info['NodeName'], Status=1)
            if not entry:
                entry = NodeInfoOrm(**location_info2.to_orm())
                nodeinfo_repo.add(entry)
                node_resource_updated = True
                node_changed = True
                self.__node_sync_q.put(node_name)
                LOG.debug("Add NodeInfo: {0}".format(entry.NodeName))
            elif not entry.Timestamp or entry.Timestamp < location_info['Timestamp']:
                # update the entry
                if entry.ResourceTypes != location_info2.ResourceTypes:
                    node_resource_updated = True
                nodeinfo_repo.update(entry.NodeName, **location_info2.to_orm())
                self.__node_sync_q.put(node_name)
                LOG.debug("Update NodeInfo: {0}".format(entry.NodeName))
            else:
                # do nothing
                LOG.debug("Ignore the location for: {0}".format(entry.NodeName))
                continue
            need_to_sync_node = True
            continue

        del nodeinfo_repo
        LOG.debug("Finished consuming location event")
        if need_to_sync_node or node_resource_updated:
            if node_changed:
                LOG.debug("signal node changed event")
                # node changes triggers rebuild map from subscription
                # due to the potential subscriptions to all nodes
                self.signal_subscription_event()
            if node_resource_updated:
                # signal the potential changes on node resources
                LOG.debug("signal node resources updating event")
                self.signal_nodeinfo_event()
            if need_to_sync_node:
                LOG.debug("signal node syncing event")
                self.signal_node_sync_event()
            self.signal_events()
        pass

    def __get_lastest_delivery_timestamp(self, node_name, subscriptionid):
        last_delivery_stat = self.notification_stat.get(node_name,{}).get(subscriptionid,{})
        last_delivery_time = last_delivery_stat.get('EventTimestamp', None)
        return last_delivery_time

    def __update_delivery_timestamp(self, node_name, subscriptionid, this_delivery_time):
        if not self.notification_stat.get(node_name, None):
            self.notification_stat[node_name] = {
                subscriptionid: {
                    'EventTimestamp': this_delivery_time
                    }
                }
            LOG.debug("delivery time @node: {0},subscription:{1} is added".format(
                node_name, subscriptionid))
        elif not self.notification_stat[node_name].get(subscriptionid, None):
            self.notification_stat[node_name][subscriptionid] = {
                'EventTimestamp': this_delivery_time
                }
            LOG.debug("delivery time @node: {0},subscription:{1} is added".format(
                node_name, subscriptionid))
        else:
            last_delivery_stat = self.notification_stat.get(node_name,{}).get(subscriptionid,{})
            last_delivery_time = last_delivery_stat.get('EventTimestamp', None)
            if (last_delivery_time >= this_delivery_time):
                return
            last_delivery_stat['EventTimestamp'] = this_delivery_time
            LOG.debug("delivery time @node: {0},subscription:{1} is updated".format(
                node_name, subscriptionid))

    def handle_notification_delivery(self, notification_info):
        LOG.debug("start notification delivery")
        result = True
        subscription_repo = None
        try:
            self.notification_lock.acquire()
            subscription_repo = SubscriptionRepo(autocommit=True)
            resource_type = notification_info.get('ResourceType', None)
            node_name = notification_info.get('ResourceQualifier', {}).get('NodeName', None)
            if not resource_type:
                raise Exception("abnormal notification@{0}".format(node_name))

            if resource_type == ResourceType.TypePTP:
                pass
            else:
                raise Exception("notification with unsupported resource type:{0}".format(resource_type))

            this_delivery_time = notification_info['EventTimestamp']

            entries = subscription_repo.get(ResourceType=resource_type, Status=1)
            for entry in entries:
                subscriptionid = entry.SubscriptionId
                ResourceQualifierJson = entry.ResourceQualifierJson or '{}'
                ResourceQualifier = json.loads(ResourceQualifierJson)
                # qualify by NodeName
                entry_node_name = ResourceQualifier.get('NodeName', None)
                node_name_matched = NodeInfoHelper.match_node_name(entry_node_name, node_name)
                if not node_name_matched:
                    continue

                subscription_dto2 = SubscriptionInfo(entry)
                try:
                    last_delivery_time = self.__get_lastest_delivery_timestamp(node_name, subscriptionid)
                    if last_delivery_time and last_delivery_time >= this_delivery_time:
                        # skip this entry since already delivered
                        LOG.debug("Ignore the notification for: {0}".format(entry.SubscriptionId))
                        continue

                    subscription_helper.notify(subscription_dto2, notification_info)
                    LOG.debug("notification is delivered successfully to {0}".format(
                        entry.SubscriptionId))

                    self.__update_delivery_timestamp(node_name, subscriptionid, this_delivery_time)

                except Exception as ex:
                    LOG.warning("notification is not delivered to {0}:{1}".format(
                        entry.SubscriptionId, str(ex)))
                    # proceed to next entry
                    continue
                finally:
                    pass
        except Exception as ex:
            LOG.warning("Failed to delivery notification:{0}".format(str(ex)))
            result = False
        finally:
            self.notification_lock.release()
            if not subscription_repo:
                del subscription_repo

        if result:
            LOG.debug("Finished notification delivery")
        else:
            LOG.warning("Failed on notification delivery")
        return result

    def process_sync_node_event(self):
        LOG.debug("Start processing sync node event")
        need_to_sync_node_again = False

        while not self.__node_sync_q.empty():
            broker_node_name = self.__node_sync_q.get(False)
            try:
                result = self.syncup_node(broker_node_name)
                if not result:
                    need_to_sync_node_again = True
            except Exception as ex:
                LOG.warning("Failed to syncup node{0}:{1}".format(broker_node_name, str(ex)))
                continue

        if need_to_sync_node_again:
            # continue try in to next loop
            self.signal_node_sync_event()
            self.signal_events()
        LOG.debug("Finished processing sync node event")

    def run(self):
        # start location listener
        self.__start_watch_all_nodes()
        while True:
            self.event.wait()
            self.event.clear()
            LOG.debug("daemon control event is asserted")

            if self.location_event.is_set():
                self.location_event.clear()
                # process location notifications
                self.consume_location_event()

            if self.subscription_event.is_set():
                self.subscription_event.clear()
                # build node resources map from subscriptions
                self.process_subscription_event()

            if self.__node_info_event.is_set():
                self.__node_info_event.clear()
                # update node_resources_map from node info
                self.__update_map_from_nodeinfos()

            if self.__node_resources_event.is_set():
                self.__node_resources_event.clear()
                # update watchers from node_resources_map
                self.__refresh_watchers_from_map()

            if self.__node_sync_event.is_set():
                self.__node_sync_event.clear()
                # compensate for the possible loss of notification during reconnection
                self.process_sync_node_event()

            continue
        return

    def syncup_resource(self, broker_node_name, resource_type):
        # check to sync up resource status on a node
        LOG.debug("sync up resource@{0} :{1}".format(broker_node_name, resource_type))
        try:
            if broker_node_name == NodeInfoHelper.BROKER_NODE_ALL:
                self.locationservice_client.trigger_publishing_status(
                    resource_type, timeout=5, retry=10)
                return True

            # 1, query resource status
            broker_client = self.notificationservice_clients.get(broker_node_name, None)
            if not broker_client:
                raise Exception("notification service client is not setup for node {0}".format(broker_node_name))
            resource_status = broker_client.query_resource_status(
                resource_type, timeout=5, retry=10)

            # 2, deliver resource by comparing LastDelivery time with EventTimestamp
            # 3, update the LastDelivery with EventTimestamp
            self.__NotificationWatcher.handle(resource_status)
        except oslo_messaging.exceptions.MessagingTimeout as ex:
            LOG.warning("Fail to syncup resource {0}@{1}, due to {2}".format(
                resource_type, broker_node_name, str(ex)))
            return False
        except Exception as ex:
            LOG.warning("Fail to syncup resource {0}@{1}, due to {2}".format(
                resource_type, broker_node_name, str(ex)))
            raise ex
        finally:
            pass
        return True

    def syncup_node(self, broker_node_name):
        all_resource_synced = True
        # check to sync up resources status on a node
        node_resources = self.node_resources_map.get(broker_node_name, None)
        if node_resources:
            LOG.debug("sync up resources@{0} :{1}".format(broker_node_name, node_resources))
            for resource_type, iteration in node_resources.items():
                if iteration == self.node_resources_iteration:
                    result = self.syncup_resource(broker_node_name, resource_type)
                    if not result:
                        all_resource_synced = False
        return all_resource_synced

    def __cleanup_map(self):
        for broker_node_name, node_resources in self.node_resources_map.items():
            resourcetypelist = [r for (r, i) in node_resources.items() if i<self.node_resources_iteration]
            for r in resourcetypelist:
                node_resources.pop(r)
            if len(node_resources) == 0:
                self.node_resources_map[broker_node_name] = None

        nodes = [n for (n, r) in self.node_resources_map.items() if not r]
        for n in nodes:
            self.node_resources_map.pop(n)
        return

    '''build map from subscriptions: {node_name:{resource_type:true}'''
    def __build_map_from_subscriptions(self):
        # increase iteration
        self.node_resources_iteration = self.node_resources_iteration+1
        subscription_repo = None

        try:
            subscription_repo = SubscriptionRepo(autocommit=True)
            subs = subscription_repo.get()
            LOG.debug("found {0} subscriptions".format(subs.count()))
            for s in subs:
                subinfo = SubscriptionInfo(s)
                LOG.debug("subscription:{0}, Status:{1}".format(subinfo.to_dict(), s.Status))

                # assume PTP and not wildcast
                resource_type = s.ResourceType
                if resource_type == ResourceType.TypePTP:
                    broker_node_name = subinfo.ResourceQualifier.NodeName
                else:
                    # ignore the subscription due to unsupported type
                    LOG.debug("Ignore the subscription for: {0}".format(subinfo.SubscriptionId))
                    continue

                if s.Status == 1:
                    current_node_name = NodeInfoHelper.expand_node_name(broker_node_name)

                    node_map = self.node_resources_map.get(current_node_name, None)
                    if not node_map:
                        node_map = {}
                        self.node_resources_map[current_node_name] = node_map
                    node_map[resource_type] = self.node_resources_iteration
                    # update the initial delivery timestamp as well

                    self.__update_delivery_timestamp(
                        NodeInfoHelper.default_node_name(broker_node_name),
                        s.SubscriptionId, s.InitialDeliveryTimestamp)

            # delete all entry with Status == 0
            subscription_repo.delete(Status=0)
        finally:
            del subscription_repo
        return True

    def __update_map_from_nodeinfos(self):
        '''Hanlde changes of ResourceTypes'''
        node_resources_map_updated = False
        result = False
        nodeinfo_repo = NodeRepo(autocommit=True)
        LOG.debug("Start node updating event")
        try:
            nodeinfos = nodeinfo_repo.get()
            for nodeinfo in nodeinfos:
                supported_resource_types = json.loads(nodeinfo.ResourceTypes or '[]')
                node_map = self.node_resources_map.get(nodeinfo.NodeName, {})
                for t, v in node_map.items():
                    if v == self.node_resources_iteration and not t in supported_resource_types:
                        # remove the resource type request by decrease the iteration
                        node_map[t] = self.node_resources_iteration - 1
                        node_resources_map_updated = True
                        LOG.warning("Detected unavailable resource type: {0}@{1}".format(t, nodeinfo.NodeName))
                    else:
                        continue
                pass
        except Exception as ex:
            LOG.warning("Failed to update map from nodeinfo:{0}".format(str(ex)))
        finally:
            del nodeinfo_repo
        LOG.debug("Finished node updating event")
        if node_resources_map_updated:
            self.signal_node_resources_event()
            self.signal_events()
            result = True
        return result

    def __start_watch_resource(self, broker_node_name, resource_type):
        # 1, check and run notificationservice client
        broker_client = self.notificationservice_clients.get(broker_node_name, None)
        if not broker_client:
            broker_client = self.__create_client(broker_node_name)
            self.notificationservice_clients[broker_node_name] = broker_client

        # 2, check and enable resource status watcher
        if not broker_client.is_listening_on_resource(resource_type):
            # must make sure the location is updated/watched:
            # check and start location watcher
            if not self.locationservice_client.is_listening_on_location(broker_node_name):
                # start watching on the location announcement
                self.locationservice_client.add_location_listener(
                    broker_node_name,
                    location_handler=self.__NodeInfoWatcher)
                LOG.debug("Start watching location announcement of notificationservice@{0}"
                .format(broker_node_name))
                # try to update location by query
                try:
                    self.locationservice_client.update_location(
                        broker_node_name, timeout=5, retry=2)
                    LOG.debug("Updated location of notificationservice@{0}".format(broker_node_name))
                except Exception as ex:
                    LOG.warning("Failed to update location of node:{0} due to: {1}".format(
                        broker_node_name, str(ex)))
                    pass
            broker_client.add_resource_status_listener(
                resource_type, status_handler=self.__NotificationWatcher)
            LOG.debug("Start watching {0}@{1}".format(resource_type, broker_node_name))
        else:
            # check if node_info has been updated, if yes, query the latest resource status
            pass

        return True

    def __stop_watch_resource(self, broker_node_name, resource_type):
        broker_client = self.notificationservice_clients.get(broker_node_name, None)
        # 1, disable resource status watcher
        if broker_client and broker_client.is_listening_on_resource(resource_type):
            broker_client.remove_resource_status_listener(resource_type)
            LOG.debug("Stop watching {0}@{1}".format(resource_type, broker_node_name))
        return True

    def __refresh_location_watcher(self):
        # update location watchers
        for broker_node_name, broker_client in self.notificationservice_clients.items():
            if not broker_client:
                continue
            if broker_client.any_listener():
                # check and start location watcher
                if not self.locationservice_client.is_listening_on_location(broker_node_name):
                    # start watching on the location announcement
                    self.locationservice_client.add_location_listener(
                        broker_node_name,
                        location_handler=self.__NodeInfoWatcher)
                    LOG.debug("Start watching location announcement of notificationservice@{0}"
                    .format(broker_node_name))
                    # update location by query
                    try:
                        self.locationservice_client.update_location(
                            broker_node_name, timeout=5, retry=2)
                        LOG.debug("Updated location of notificationservice@{0}".format(broker_node_name))
                    except Exception as ex:
                        LOG.debug("Failed to Updated location of notificationservice@{0}".format(
                            broker_node_name))
                        continue
                else:
                    pass
            elif self.locationservice_client.is_listening_on_location(broker_node_name):
                # 1, stop location listener
                self.locationservice_client.remove_location_listener(broker_node_name)
                LOG.debug("Stop watching location announcement for node@{0}"
                .format(broker_node_name))
                # 2, remove broker client
                self.notificationservice_clients[broker_node_name] = None
                del broker_client
                LOG.debug("Stop watching notificationservice@{0}".format(broker_node_name))
            else:
                pass
            return

    def process_subscription_event(self):
        # get subscriptions from DB
        result = self.__build_map_from_subscriptions()
        if result:
            # need update map with nodeinfo after rebuilding the map
            self.signal_nodeinfo_event()
            self.signal_node_resources_event()
            self.signal_events()

    def __start_watch_all_nodes(self, retry_interval=5):
        try:
            while not self.locationservice_client.is_listening_on_location(
                NodeInfoHelper.BROKER_NODE_ALL):
                # start watching on the location announcement
                self.locationservice_client.add_location_listener(
                    NodeInfoHelper.BROKER_NODE_ALL,
                    location_handler=self.__NodeInfoWatcher)
                LOG.debug(
                    "Start watching location announcement of notificationservice@{0}"
                    .format(NodeInfoHelper.BROKER_NODE_ALL))
                if not self.locationservice_client.is_listening_on_location(
                    NodeInfoHelper.BROKER_NODE_ALL):
                    # retry later and forever
                    time.sleep(retry_interval)
            self.locationservice_client.trigger_location_annoucement(timeout=20, retry=10)
        except Exception as ex:
            LOG.debug("exception: {0}".format(str(ex)))
            pass
        finally:
            pass
        return

    def __refresh_watchers_from_map(self):
        try:
            LOG.debug("refresh with {0} nodes".format(len(self.node_resources_map)))
            node_to_sync = []
            for broker_node_name, node_resources in self.node_resources_map.items():
                LOG.debug("check to watch resources@{0} :{1}".format(broker_node_name, node_resources))
                need_to_sync_node = False
                for resource_type, iteration in node_resources.items():
                    # enable watchers
                    if iteration == self.node_resources_iteration:
                        self.__start_watch_resource(broker_node_name, resource_type)
                        need_to_sync_node = True
                    else:
                        self.__stop_watch_resource(broker_node_name, resource_type)
                if need_to_sync_node:
                    node_to_sync.append(broker_node_name)
            self.__refresh_location_watcher()
            self.__cleanup_map()
            if node_to_sync:
                # trigger the node sync up event
                for node_name in node_to_sync:
                    self.__node_sync_q.put(node_name)
                self.signal_node_sync_event()
                self.signal_events()
        except Exception as ex:
            LOG.debug("exception: {0}".format(str(ex)))
            pass
        finally:
            pass
        return

    def __create_client(self, broker_node_name):
        if broker_node_name == NodeInfoHelper.BROKER_NODE_ALL:
            # special case: if monitor all node, then use the same broker as locationservice
            return self.locationservice_client
        broker_host = "notificationservice-{0}".format(broker_node_name)
        broker_transport_endpoint = "rabbit://{0}:{1}@{2}:{3}".format(
            self.daemon_context['NOTIFICATION_BROKER_USER'],
            self.daemon_context['NOTIFICATION_BROKER_PASS'],
            broker_host,
            self.daemon_context['NOTIFICATION_BROKER_PORT'])
        return NotificationServiceClient(broker_node_name, broker_transport_endpoint)


class DaemonControl(object):

    def __init__(self, daemon_context, process_worker = None):
        self.daemon_context = daemon_context
        self.residing_node_name = daemon_context['THIS_NODE_NAME']
        self.event = mp.Event()
        self.subscription_event = mp.Event()
        self.registration_endpoint = RpcEndpointInfo(daemon_context['REGISTRATION_TRANSPORT_ENDPOINT'])
        self.registration_transport = rpc_helper.get_transport(self.registration_endpoint)
        self.locationservice_client = LocationServiceClient(self.registration_endpoint.TransportEndpoint)

        if not process_worker:
            process_worker = ProcessWorkerDefault

        self.mpinstance = mp.Process( target=process_worker, args=(
            self.event, self.subscription_event, daemon_context))
        self.mpinstance.start()
        # initial update
        self.refresh()
        pass

    def refresh(self):
        self.subscription_event.set()
        self.event.set()
