#
# Copyright (c) 2021-2022 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import json
import logging

import multiprocessing as mp
import threading
import sys

if sys.version > '3':
    import queue as Queue
else:
    import Queue

from notificationclientsdk.common.helpers import subscription_helper
from notificationclientsdk.common.helpers.nodeinfo_helper import NodeInfoHelper
from notificationclientsdk.common.helpers import log_helper

from notificationclientsdk.model.dto.subscription import SubscriptionInfoV1
from notificationclientsdk.model.dto.resourcetype import ResourceType
from notificationclientsdk.model.dto.location import LocationInfo

from notificationclientsdk.repository.dbcontext import DbContext
from notificationclientsdk.repository.subscription_repo import SubscriptionRepo

from notificationclientsdk.model.orm.node import NodeInfo as NodeInfoOrm

from notificationclientsdk.repository.node_repo import NodeRepo

from notificationclientsdk.client.locationservice import LocationHandlerBase

from notificationclientsdk.services.broker_state_manager import \
    BrokerStateManager
from notificationclientsdk.services.broker_connection_manager import \
    BrokerConnectionManager
from notificationclientsdk.services.notification_handler import \
    NotificationHandler

LOG = logging.getLogger(__name__)
log_helper.config_logger(LOG)


class NotificationWorker:
    class LocationInfoHandler(LocationHandlerBase):
        '''Glue code to forward location info to daemon method'''
        def __init__(self, locationinfo_dispatcher):
            self.locationinfo_dispatcher = locationinfo_dispatcher
            super(NotificationWorker.LocationInfoHandler, self).__init__()

        def handle(self, location_info):
            LOG.debug("Received location info:{0}".format(location_info))
            return self.locationinfo_dispatcher.produce_location_event(
                location_info)

    def __init__(self, event, subscription_event, daemon_context,
                 service_nodenames):
        self.__alive = True

        self.daemon_context = daemon_context
        NodeInfoHelper.set_residing_node(daemon_context['THIS_NODE_NAME'])

        self.sqlalchemy_conf = json.loads(
            daemon_context['SQLALCHEMY_CONF_JSON'])
        DbContext.init_dbcontext(self.sqlalchemy_conf)
        self.event = event
        self.subscription_event = subscription_event

        self.service_nodenames = service_nodenames

        self.__locationinfo_handler = \
            NotificationWorker.LocationInfoHandler(self)
        self.__notification_handler = NotificationHandler()
        self.broker_connection_manager = BrokerConnectionManager(
            self.__locationinfo_handler,
            self.__notification_handler,
            self.daemon_context)
        self.broker_state_manager = BrokerStateManager()

        self.__init_location_channel()

        # event to signal brokers state change
        self.__brokers_watcher_event = mp.Event()
        self.__brokers_data_syncup_event = mp.Event()

    def __init_location_channel(self):
        self.location_event = mp.Event()
        self.location_lock = threading.Lock()
        # only cache the latest loation info
        self.location_channel = {}
        self.location_keys_q = Queue.Queue()

    def signal_events(self):
        self.event.set()

    def produce_location_event(self, location_info):
        node_name = location_info.get('NodeName', None)
        podip = location_info.get("PodIP", None)
        if not node_name or not podip:
            LOG.warning(
                "Missing PodIP inside location info:{0}".format(location_info))
            return False
        timestamp = location_info.get('Timestamp', 0)
        # mutex for threads which produce location events
        self.location_lock.acquire()
        try:
            current = self.location_channel.get(node_name, {})
            if current.get('Timestamp', 0) < timestamp:
                # update with the location_info
                self.location_channel[node_name] = location_info
                self.location_keys_q.put(node_name)
                # notify the consumer to process the update
                self.location_event.set()
                self.signal_events()
                return True
        except Exception as ex:
            LOG.warning("failed to produce location event:{0}".format(str(ex)))
            return False
        finally:
            # release lock
            self.location_lock.release()

    def run(self):
        self.broker_connection_manager.start()
        while self.__alive:
            self.event.wait()
            self.event.clear()
            LOG.debug("daemon control event is asserted")

            if self.location_event.is_set():
                self.location_event.clear()
                # update location information
                self.consume_location_event()

            if self.subscription_event.is_set():
                self.subscription_event.clear()
                # refresh brokers state from subscriptions
                self.handle_subscriptions_event()

            if self.__brokers_watcher_event.is_set():
                self.__brokers_watcher_event.clear()
                # sync up brokers connection with their state
                self.handle_brokers_watcher_event()

            if self.__brokers_data_syncup_event.is_set():
                self.__brokers_data_syncup_event.clear()
                # sync up broker's data
                self.handle_brokers_data_syncup_event()

            continue

        self.broker_connection_manager.stop()

    def consume_location_event(self):
        nodeinfo_repo = None
        try:
            LOG.debug("Start to consume location event")
            _nodeinfo_added = 0
            _nodeinfo_updated = 0
            nodeinfo_repo = NodeRepo(autocommit=True)

            while not self.location_keys_q.empty():
                node_name = self.location_keys_q.get(False)
                location_info = self.location_channel.get(node_name, None)
                if not location_info:
                    LOG.warning(
                        "ignore location info@{0} without content".format(
                            node_name))
                    continue

                LOG.debug("consume location info @{0}:{1}".format(
                    node_name, location_info))
                is_nodeinfo_added, is_nodeinfo_updated = \
                    self.__persist_locationinfo(location_info, nodeinfo_repo)
                _nodeinfo_added = \
                    _nodeinfo_added + (1 if is_nodeinfo_added else 0)
                if is_nodeinfo_added and \
                        node_name not in self.service_nodenames:
                    self.service_nodenames.append(node_name)
                    LOG.debug("List of nodes updated: id %d contents %s" %
                              (id(self.service_nodenames),
                               self.service_nodenames))
                _nodeinfo_updated = \
                    _nodeinfo_updated + (1 if is_nodeinfo_updated else 0)
                continue

            LOG.debug("Finished consuming location event")

            if _nodeinfo_added > 0:
                LOG.debug(
                    "signal event to refresh brokers state from subscription")
                # node info changes trigger rebuilding broker states from
                # subscription due to some subscriptions might subscribe
                # resources of all nodes
                self.subscription_event.set()

            if _nodeinfo_added > 0 or _nodeinfo_updated > 0:
                LOG.debug(
                    "try to refresh brokers state due to changes of node info")
                nodeinfos = nodeinfo_repo.get()
                broker_state_changed = \
                    self.broker_state_manager.refresh_by_nodeinfos(nodeinfos)
                if broker_state_changed:
                    # signal the potential changes on node resources
                    LOG.debug("signal event to re-sync up brokers state")
                    self.__brokers_watcher_event.set()
                    self.signal_events()

        except Exception as ex:
            LOG.warning("failed to consume location event:{0}".format(str(ex)))
        finally:
            if nodeinfo_repo:
                del nodeinfo_repo

    def handle_subscriptions_event(self):
        broker_state_changed = self.__update_broker_with_subscription()
        if broker_state_changed:
            self.__brokers_watcher_event.set()
            self.signal_events()

    def __persist_locationinfo(self, location_info, nodeinfo_repo):
        is_nodeinfo_added = False
        is_nodeinfo_updated = False
        try:
            location_info2 = LocationInfo(**location_info)
            entry = nodeinfo_repo.get_one(
                NodeName=location_info['NodeName'], Status=1)
            if not entry:
                entry = NodeInfoOrm(**location_info2.to_orm())
                nodeinfo_repo.add(entry)
                is_nodeinfo_added = True
                LOG.debug("Add NodeInfo: {0}".format(entry.NodeName))
            elif not entry.Timestamp or (entry.Timestamp <
                                         location_info['Timestamp']):
                # location info with newer timestamp indicate broker need to be
                # re-sync up
                is_nodeinfo_updated = True
                nodeinfo_repo.update(entry.NodeName, **location_info2.to_orm())
                LOG.debug("Update NodeInfo: {0}".format(entry.NodeName))
            else:
                # do nothing
                LOG.debug("Ignore the location for broker: {0}".format(
                    entry.NodeName))
        except Exception as ex:
            LOG.warning("failed to update broker state with "
                        "location info:{0},{1}".format(location_info,
                                                       str(ex)))
        finally:
            return is_nodeinfo_added, is_nodeinfo_updated

    def __update_broker_with_subscription(self):
        '''update broker state with subscriptions'''
        broker_state_changed = False
        subscription_repo = None
        nodeinfo_repo = None

        try:
            subscription_repo = SubscriptionRepo(autocommit=True)
            nodeinfo_repo = NodeRepo(autocommit=True)
            subs = subscription_repo.get()
            LOG.debug("found {0} subscriptions".format(subs.count()))
            broker_state_changed = \
                self.broker_state_manager.refresh_by_subscriptions(subs)
            if broker_state_changed:
                nodeinfo_repo = NodeRepo(autocommit=True)
                nodeinfos = nodeinfo_repo.get()
                self.broker_state_manager.refresh_by_nodeinfos(nodeinfos)

            for s in subs:
                if s.ResourceType:
                    subinfo = SubscriptionInfoV1(s)
                    # assume resource type being PTP and not wildcard
                    resource_type = s.ResourceType
                    if resource_type == ResourceType.TypePTP:
                        broker_name = subinfo.ResourceQualifier.NodeName
                    else:
                        # ignore the subscription due to unsupported type
                        LOG.debug(
                            "Ignore the subscription for: {0}".format(
                                subinfo.SubscriptionId))
                        continue
                elif s.ResourceAddress:
                    # Get nodename from resource address
                    LOG.info(
                        "Parse resource address {}".format(s.ResourceAddress))
                    _, nodename, _, _, _ = \
                        subscription_helper.parse_resource_address(
                            s.ResourceAddress)
                    broker_name = nodename
                else:
                    LOG.debug("Subscription {} does not have ResourceType or "
                              "ResourceAddress".format(s.SubscriptionId))
                    continue

                if s.Status == 1:
                    # update the initial delivery timestamp as well
                    self.__notification_handler.update_delivery_timestamp(
                        NodeInfoHelper.default_node_name(broker_name),
                        s.SubscriptionId, s.InitialDeliveryTimestamp)

            # delete all entry with Status == 0
            subscription_repo.delete(Status=0)
        finally:
            del subscription_repo
            del nodeinfo_repo
        return broker_state_changed

    def handle_brokers_watcher_event(self):
        result = False
        try:
            LOG.debug("try to sync up watcher for {0} brokers".format(
                self.broker_state_manager.count_brokers()))
            result, _, _ = self.broker_state_manager.syncup_broker_watchers(
                self.broker_connection_manager)
            self.__brokers_data_syncup_event.set()
        except Exception as ex:
            result = False
            LOG.warning(
                "fail to sync up watcher for brokers: {0}".format(str(ex)))
        finally:
            if not result:
                # retry indefinitely
                self.__brokers_watcher_event.set()
                self.signal_events()

    def handle_brokers_data_syncup_event(self):
        result = False
        try:
            LOG.debug("try to sync up  data for {0} brokers".format(
                self.broker_state_manager.count_brokers()))
            result, _, _ = self.broker_state_manager.syncup_broker_data(
                self.broker_connection_manager)
        except Exception as ex:
            result = False
            LOG.warning(
                "fail to sync up data for brokers: {0}".format(str(ex)))
        finally:
            if not result:
                self.__brokers_data_syncup_event.set()
                self.signal_events()
