#
# Copyright (c) 2021 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from sqlalchemy import Float, Integer, ForeignKey, String, Column

from notificationclientsdk.model.orm.base import OrmBase

class Subscription(OrmBase):
    __tablename__ = 'subscription'
    SubscriptionId = Column(String(128), primary_key=True)
    UriLocation = Column(String(512))
    ResourceType = Column(String(64))
    EndpointUri = Column(String(512))
    InitialDeliveryTimestamp = Column(Float)
    Status = Column(Integer)
    CreateTime = Column(Float)
    LastUpdateTime = Column(Float)
    ResourceQualifierJson = Column(String)

def create_tables(orm_engine):
    Subscription.metadata.create_all(orm_engine)
