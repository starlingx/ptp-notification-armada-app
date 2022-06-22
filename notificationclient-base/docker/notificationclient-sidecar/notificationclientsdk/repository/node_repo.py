#
# Copyright (c) 2021 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import time, uuid
import logging

from sqlalchemy.orm         import scoped_session, sessionmaker

from notificationclientsdk.model.orm.node import NodeInfo as NodeInfoOrm
from notificationclientsdk.repository.dbcontext import DbContext

LOG = logging.getLogger(__name__)

from notificationclientsdk.common.helpers import log_helper
log_helper.config_logger(LOG)

class NodeRepo(DbContext):
    def __init__(self, session=None, autocommit=False):
        self.autocommit = autocommit
        super(NodeRepo, self).__init__(session)
        if session:
            self.own_session = False
        else:
            self.own_session = True

    def __del__(self):
        if self.own_session:
            self.clear()

    def add(self, nodeinfo):
        try:
            nodeinfo.Status = 1
            nodeinfo.CreateTime = time.time()
            nodeinfo.LastUpdateTime = nodeinfo.CreateTime
            self.session.add(nodeinfo)
        except Exception as ex:
            if self.autocommit:
                self.rollback()
            raise ex
        else:
            if self.autocommit:
                self.commit()
            return nodeinfo

    def update(self, node_name, **data):
        try:
            data['LastUpdateTime'] = time.time()
            self.session.query(NodeInfoOrm).filter_by(NodeName=node_name).update(data)
        except Exception as ex:
            if self.autocommit:
                self.rollback()
            raise ex
        else:
            if self.autocommit:
                self.commit()

    def get_one(self, **filter):
        return self.session.query(NodeInfoOrm).filter_by(**filter).first()

    def get(self, **filter):
        return self.session.query(NodeInfoOrm).filter_by(**filter)

    def delete_one(self, **filter):
        try:
            entry = self.session.query(NodeInfoOrm).filter_by(**filter).first()
            self.session.delete(entry)
        except Exception as ex:
            if self.autocommit:
                self.rollback()
            raise ex
        else:
            if self.autocommit:
                self.commit()

    def delete(self, **filter):
        try:
            entry = self.session.query(NodeInfoOrm).filter_by(**filter).delete()
        except Exception as ex:
            if self.autocommit:
                self.rollback()
            raise ex
        else:
            if self.autocommit:
                self.commit()
