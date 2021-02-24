#
# Copyright (c) 2021 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import sqlalchemy
from sqlalchemy import MetaData
from sqlalchemy.ext.declarative import declarative_base

DefaultMetaData = MetaData()
OrmBase = declarative_base(metadata = DefaultMetaData) #生成orm基类

def create_tables(orm_engine):
    OrmBase.metadata.create_all(orm_engine) #创建表结构
    return OrmBase.metadata
