#coding=utf-8
#
# Copyright (c) 2021 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import os
import json
from wsme import types as wtypes
import datetime
import time

import uuid

from notificationclientsdk.model.dto.resourcetype import EnumResourceType, ResourceType

'''
Base for Resource Qualifiers
'''
class ResourceQualifierBase(wtypes.Base):
    def __init__(self, **kw):
        super(ResourceQualifierBase, self).__init__(**kw)
    
    def to_dict(self):
        pass


'''
Resource Qualifiers PTP
'''
class ResourceQualifierPtp(ResourceQualifierBase):
    NodeName = wtypes.text

    def __init__(self, **kw):
        self.NodeName = kw.pop('NodeName', None)
        super(ResourceQualifierPtp, self).__init__(**kw)
    
    def to_dict(self):
        d = {
            'NodeName': self.NodeName
        }
        return d

'''
ViewModel of Subscription
'''
class SubscriptionInfoV0(wtypes.Base):
    SubscriptionId = wtypes.text
    UriLocation = wtypes.text
    ResourceType = EnumResourceType
    EndpointUri = wtypes.text

    # dynamic type depending on ResourceType
    def set_resource_qualifier(self, value):
        if isinstance(value, wtypes.Base):
            self._ResourceQualifer = value
        else:
            self._ResourceQualifierJson = value
            self._ResourceQualifer = None

    def get_resource_qualifier(self):
        if not self._ResourceQualifer:
            if self.ResourceType == ResourceType.TypePTP:
                self._ResourceQualifer = ResourceQualifierPtp(**self._ResourceQualifierJson)
            else:
                self._ResourceQualifer = None
        return self._ResourceQualifer

    ResourceQualifier = wtypes.wsproperty(wtypes.Base,
    get_resource_qualifier, set_resource_qualifier)


    def __init__(self, orm_entry=None):
        if orm_entry:
            self.SubscriptionId = orm_entry.SubscriptionId
            self.ResourceType = orm_entry.ResourceType
            self.UriLocation = orm_entry.UriLocation
            self.ResourceQualifier = json.loads(orm_entry.ResourceQualifierJson)
            self.EndpointUri = orm_entry.EndpointUri

    def to_dict(self):
        d = {
                'SubscriptionId': self.SubscriptionId,
                'ResourceType': self.ResourceType,
                'UriLocation': self.UriLocation,
                'EndpointUri': self.EndpointUri,
                'ResourceQualifier': self.ResourceQualifier.to_dict(),
            }
        return d

    def to_orm(self):
        d = {
                'SubscriptionId': self.SubscriptionId,
                'ResourceType': self.ResourceType or '',
                'UriLocation': self.UriLocation,
                'EndpointUri': self.EndpointUri or '',
                'ResourceQualifierJson': json.dumps(self.ResourceQualifier.to_dict())  or '',
            }
        return d

class SubscriptionInfoV1(wtypes.Base):
    SubscriptionId = wtypes.text
    UriLocation = wtypes.text
    EndpointUri = wtypes.text
    ResourceAddress = wtypes.text

    def __init__(self, orm_entry=None):
        if orm_entry:
            self.SubscriptionId = orm_entry.SubscriptionId
            self.UriLocation = orm_entry.UriLocation
            self.EndpointUri = orm_entry.EndpointUri
            self.ResourceAddress = orm_entry.ResourceAddress

    def to_dict(self):
        d = {
                'SubscriptionId': self.SubscriptionId,
                'UriLocation': self.UriLocation,
                'EndpointUri': self.EndpointUri,
                'ResourceAddress': self.ResourceAddress,
            }
        return d

    def to_orm(self):
        d = {
                'SubscriptionId': self.SubscriptionId,
                'UriLocation': self.UriLocation,
                'EndpointUri': self.EndpointUri or '',
                'ResourceAddress': self.ResourceAddress or ''
            }
        return d
