#
# Copyright (c) 2021 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from sqlalchemy import Float, Integer, ForeignKey, String, Column

from notificationclientsdk.model.orm.base import OrmBase

'''
NodeName: literal Node Name
ResourceTypes: json dump of Enumerate string list: PTP, FPGA, etc
'''
class NodeInfo(OrmBase):
    __tablename__ = 'nodeinfo'
    NodeName = Column(String(128), primary_key=True)
    PodIP = Column(String(256))
    ResourceTypes = Column(String(1024))
    Timestamp = Column(Float)
    Status = Column(Integer)
    CreateTime = Column(Float)
    LastUpdateTime = Column(Float)

def create_tables(orm_engine):
    NodeInfo.metadata.create_all(orm_engine)
