#coding=utf-8
#
# Copyright (c) 2021 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import json

from wsme import types as wtypes
from notificationclientsdk.model.dto.resourcetype import EnumResourceType

class BrokerState(wtypes.Base):
    BrokerName = wtypes.text
    # Timestamp = float
    Connected = bool
    ConnectionStateChanged = bool
    BrokerIP = wtypes.text
    BrokerIPChanged = bool
    ResourceTypes = [EnumResourceType]
    ResourceTypesChanged = bool
    ResourceTypesSubscribed = {wtypes.text:int}
    ResourceTypesSubscribedChanged = bool
    DataSyncupPendingDetails = [wtypes.text]

    def update_connection_state(self, is_connected):
        if self.Connected != is_connected:
            self.Connected = is_connected
            self.ConnectionStateChanged = True
        return self.ConnectionStateChanged

    def is_connected(self):
        return self.Connected

    def is_connection_state_changed(self):
        return self.ConnectionStateChanged

    def ack_connection_state_changed(self):
        self.ConnectionStateChanged = False

    def update_broker_ip(self, broker_ip):
        if self.BrokerIP != broker_ip:
            self.BrokerIP = broker_ip
            self.BrokerIPChanged = True
        return self.BrokerIPChanged

    def is_broker_ip_changed(self):
        return self.BrokerIPChanged

    def ack_broker_ip_changed(self):
        self.BrokerIPChanged = False

    def update_resources(self, resources_list):
        sorted_resource_list = resources_list.sort()
        if self.ResourceTypes != sorted_resource_list:
            self.ResourceTypes = sorted_resource_list
            self.ResourceTypesChanged = True
        return self.ResourceTypesChanged

    def is_resources_changed(self):
        return self.ResourceTypesChanged

    def ack_resources_changed(self):
        self.ResourceTypesChanged = False

    def any_resource_subscribed(self):
        return len(self.ResourceTypesSubscribed) > 0

    def try_subscribe_resource(self, resource_type, indicator):
        self.ResourceTypesSubscribedChanged = self.ResourceTypesSubscribedChanged or not resource_type in self.ResourceTypesSubscribed
        self.ResourceTypesSubscribed[resource_type] = indicator

    def try_unsubscribe_resource(self, resource_type):
        self.ResourceTypesSubscribedChanged = self.ResourceTypesSubscribedChanged or resource_type in self.ResourceTypesSubscribed
        self.ResourceTypesSubscribed.pop(resource_type, None)

    def is_resource_subscribed_changed(self):
        return self.ResourceTypesSubscribedChanged

    def ack_resource_subscribed_changed(self):
        self.ResourceTypesSubscribedChanged = False

    def is_resource_subscribed(self, resource_type):
        return resource_type in self.ResourceTypesSubscribed

    def any_obsolete_subscription(self, indicator):
        for s, i in self.ResourceTypesSubscribed.items():
            if i != indicator:
                return True
        return False

    def any_resource_subscribed(self):
        return len(self.ResourceTypesSubscribed) > 0

    def unsubscribe_resource_obsolete(self, indicator):
        uninterested = []
        for s, i in self.ResourceTypesSubscribed.items():
            if i != indicator:
                uninterested.append(s)
        for s in uninterested:
            self.ResourceTypesSubscribed.pop(s, None)
        return len(uninterested) > 0

    def signal_data_syncup(self, resource_type=None):
        if not resource_type:
            self.DataSyncupPendingDetails = [k for k,v in self.ResourceTypesSubscribed.items()]
        elif resource_type not in self.ResourceTypesSubscribed:
            return False
        elif not resource_type in self.DataSyncupPendingDetails:
            self.DataSyncupPendingDetails.append(resource_type)
        return True

    def ack_data_syncup(self, resource_type=None):
        if not resource_type:
            self.DataSyncupPendingDetails = []
        elif resource_type in self.DataSyncupPendingDetails:
            self.DataSyncupPendingDetails.remove(resource_type)

    def is_data_syncup(self, resource_type=None):
        if not resource_type:
            return len(self.DataSyncupPendingDetails or []) > 0
        else:
            return not resource_type in self.DataSyncupPendingDetails or []