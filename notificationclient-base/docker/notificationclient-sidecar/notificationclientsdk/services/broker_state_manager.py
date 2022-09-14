#
# Copyright (c) 2021-2022 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import json
import logging
from notificationclientsdk.model.dto.subscription import SubscriptionInfoV1
from notificationclientsdk.model.dto.subscription import SubscriptionInfoV2
from notificationclientsdk.model.dto.resourcetype import ResourceType
from notificationclientsdk.common.helpers.nodeinfo_helper import NodeInfoHelper
from notificationclientsdk.common.helpers import subscription_helper

from notificationclientsdk.model.dto.broker_state import BrokerState

LOG = logging.getLogger(__name__)

from notificationclientsdk.common.helpers import log_helper

log_helper.config_logger(LOG)


class BrokerStateManager:
    '''
    Manager to manage broker states
    Note: Now it is not thread safe
    '''

    def __init__(self):
        self.broker_state_map = {}
        self.disabled_brokers = []
        self.subscription_refresh_iteration = 0

    def count_brokers(self):
        return len(self.broker_state_map)

    def add_broker(self, broker_name):
        brokerstate = self.broker_state_map.get(broker_name, None)
        if not brokerstate:
            brokerstate = BrokerState(
                BrokerName=broker_name,
                ResourceTypes=[], ResourceTypesSubscribed={})
            brokerstate.update_connection_state(False)
            self.broker_state_map[broker_name] = brokerstate
        return brokerstate

    def disable_broker(self, broker_name):
        if not broker_name in self.disabled_brokers:
            self.disabled_brokers.append(broker_name)

    def remove_broker(self, broker_name):
        self.broker_state_map.pop(broker_name, None)

    def refresh_by_nodeinfos(self, nodeinfos_orm):
        broker_state_changed = False
        for s in nodeinfos_orm or []:
            broker_state_changed = self.refresh_by_nodeinfo(s) or broker_state_changed
        return broker_state_changed

    def refresh_by_nodeinfo(self, nodeinfo_orm):
        brokerstate = self.broker_state_map.get(nodeinfo_orm.NodeName, None)
        if not brokerstate:
            return False
        if nodeinfo_orm.Status == 1:
            brokerstate.update_connection_state(True)
        else:
            brokerstate.update_connection_state(False)
        brokerstate.update_broker_ip(nodeinfo_orm.PodIP)
        brokerstate.update_resources(json.loads(nodeinfo_orm.ResourceTypes))
        return brokerstate.is_broker_ip_changed() or brokerstate.is_resources_changed()

    def refresh_by_subscriptions(self, subscriptions_orm):
        broker_state_changed = False
        # 1, refresh iteration
        self.subscription_refresh_iteration = self.subscription_refresh_iteration + 1

        # 2, refresh resource subscriptions by subscription record
        for s in subscriptions_orm or []:
            broker_state_changed = self.__refresh_by_subscription(s) or broker_state_changed

        # 3, mark broker state change by checking if any obsolete resources
        broker_state_changed = broker_state_changed or self.any_obsolete_broker()
        return broker_state_changed

    def any_obsolete_broker(self):
        for broker_name, brokerstate in self.broker_state_map.items():
            try:
                if brokerstate.any_obsolete_subscription(
                        self.subscription_refresh_iteration):
                    return True
            except Exception as ex:
                LOG.warning(
                    "failed to check obsoleted resources@{0}:{1}".format(broker_name, str(ex)))
                continue
        return False

    def __refresh_by_subscription(self, subscription_orm):
        changed = False
        broker_name = None

        if getattr(subscription_orm, 'ResourceType') is not None:
            subscription = SubscriptionInfoV1(subscription_orm)
            resource = subscription.ResourceType
            # assume PTP and not wildcard
            if resource == ResourceType.TypePTP:
                broker_name = subscription.ResourceQualifier.NodeName
            else:
                # ignore the subscription due to unsupported type
                LOG.debug(
                    "Ignore the subscription for: {0}".format(subscription_orm.SubscriptionId))
                return False
        else:
            subscription = SubscriptionInfoV2(subscription_orm)
            _, nodename, resource, _, _ = subscription_helper.parse_resource_address(
                subscription.ResourceAddress)
            broker_name = nodename

        LOG.debug(
            "subscription:{0}, Status:{1}".format(subscription.to_dict(), subscription_orm.Status))
        if subscription_orm.Status != 1:
            return False

        if not broker_name:
            # ignore the subscription due to unsupported type
            LOG.debug("Ignore the subscription for: {0}".format(subscription.SubscriptionId))
            return False

        enumerated_broker_names = NodeInfoHelper.enumerate_nodes(broker_name)
        if not enumerated_broker_names:
            LOG.debug("Failed to enumerate broker names for {0}".format(broker_name))
            return False

        for expanded_broker_name in enumerated_broker_names:
            brokerstate = self.broker_state_map.get(expanded_broker_name, None)
            if not brokerstate:
                brokerstate = self.add_broker(expanded_broker_name)
                changed = True

            changed = changed or (brokerstate.is_resource_subscribed(resource) == False)
            brokerstate.try_subscribe_resource(resource, self.subscription_refresh_iteration)

        return changed

    def syncup_broker_watchers(self, broker_connection_manager):
        '''sync up brokers state to broker connection manager'''
        aggregated_result = True
        interested_brokers = []
        removed_brokers = []
        # 1, clean all obsolete resource subscriptions
        # and disable broker in case no active resource subscription
        for broker_name, brokerstate in self.broker_state_map.items():
            try:
                brokerstate.unsubscribe_resource_obsolete(self.subscription_refresh_iteration)
                if not brokerstate.any_resource_subscribed():
                    LOG.debug("disable broker@{0} due to no subscription".format(broker_name))
                    self.disable_broker(broker_name)
            except Exception as ex:
                LOG.warning(
                    "failed to clean obsolete subscribed resources@{0}:{1}".format(
                        broker_name, str(ex)))
                continue

        # 2, stop watching all disabled brokers
        for broker_name in self.disabled_brokers:
            try:
                LOG.debug("stop watching due to disabled: {0}".format(broker_name))
                result = broker_connection_manager.stop_watching_broker(
                    broker_name)
                self.remove_broker(broker_name)
                removed_brokers.append(broker_name)
                aggregated_result = aggregated_result and result
            except Exception as ex:
                LOG.warning(
                    "failed to clean disabled broker@{0}: {1}".format(
                        broker_name, str(ex)))
                aggregated_result = False
                continue
        self.disabled_brokers.clear()

        # 3, start/restart watching remains brokers
        for broker_name, brokerstate in self.broker_state_map.items():
            interested_brokers.append(broker_name)
            try:
                result = True
                is_connected = brokerstate.is_connected()
                is_watching = broker_connection_manager.is_watching_broker(
                    broker_name)

                if not is_connected:
                    if is_watching:
                        LOG.debug("Stop watching due to disconnected: {0}".format(broker_name))
                        result = broker_connection_manager.stop_watching_broker(
                            broker_name)
                elif is_connected:
                    # note: start/restart watcher will update resources as well
                    if not is_watching:
                        LOG.debug("Start watching due to connected: {0}".format(broker_name))
                        result = broker_connection_manager.start_watching_broker(
                            brokerstate)
                    elif brokerstate.is_broker_ip_changed():
                        LOG.debug("Restart watching due to IP changed: {0}".format(broker_name))
                        result = broker_connection_manager.restart_watching_broker(
                            brokerstate)
                    elif brokerstate.is_connection_state_changed():
                        # trigger to sync up notification after (re-)connection
                        LOG.debug("Trigger to re-sync up data: {0}".format(broker_name))
                        result = brokerstate.signal_data_syncup()
                    elif brokerstate.is_resource_subscribed_changed() or \
                            brokerstate.is_resources_changed():
                        LOG.debug(
                            "Update watching due to resources changed: {0}".format(broker_name))
                        result = broker_connection_manager.update_watching_resources(brokerstate)

                # leave the signals as it is to re-sync up in next loop in case of failure
                if result:
                    # assumption to avoid race condition: same thread to manipulate brokerstate
                    brokerstate.ack_connection_state_changed()
                    brokerstate.ack_broker_ip_changed()
                    brokerstate.ack_resource_subscribed_changed()
                    brokerstate.ack_resources_changed()

                aggregated_result = aggregated_result and result
            except Exception as ex:
                LOG.warning("failed to sync up broker watcher:{0},{1}".format(broker_name, str(ex)))
                aggregated_result = False
                continue
        return aggregated_result, interested_brokers, removed_brokers

    def syncup_broker_data(self, broker_connection_manager):
        '''sync up to get rid of stall data'''
        aggregated_result = True
        synced_brokers = []
        unsynced_brokers = []
        for broker_name, brokerstate in self.broker_state_map.items():
            try:
                if brokerstate.is_connected() and brokerstate.is_data_syncup():
                    LOG.debug("Try to sync up broker data:{0}".format(broker_name))
                    result = result and broker_connection_manager.syncup_broker_data(
                        brokerstate)
                    if result:
                        # assumption to avoid race condition: same thread to manipulate brokerstate
                        brokerstate.ack_data_syncup()
                        synced_brokers.append(broker_name)
                    else:
                        unsynced_brokers.append(broker_name)
                    aggregated_result = aggregated_result and result
            except Exception as ex:
                unsynced_brokers.append(broker_name)
                LOG.warning("failed to sync up broker data:{0}".format(str(ex)))
                aggregated_result = False
                continue
        return aggregated_result, synced_brokers, unsynced_brokers
