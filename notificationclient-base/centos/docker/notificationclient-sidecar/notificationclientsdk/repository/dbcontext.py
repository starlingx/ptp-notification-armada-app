#
# Copyright (c) 2021 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import logging

from sqlalchemy             import create_engine, MetaData
from sqlalchemy.orm         import scoped_session, sessionmaker

from notificationclientsdk.model.orm import base
from notificationclientsdk.model.orm import subscription
from notificationclientsdk.model.orm import node

LOG = logging.getLogger(__name__)

from notificationclientsdk.common.helpers import log_helper
log_helper.config_logger(LOG)


class DbContext(object):
    # static properties
    DBSession = None
    metadata = None
    engine = None

    @staticmethod
    def _engine_from_config(configuration):
        configuration = dict(configuration)
        url = configuration.pop('url')
        return create_engine(url, **configuration)

    @staticmethod
    def init_dbcontext(sqlalchemy_conf):
        """
        This is a stub method which is called at application startup time.

        If you need to bind to a parsed database configuration, set up tables or
        ORM classes, or perform any database initialization, this is the
        recommended place to do it.

        For more information working with databases, and some common recipes,
        see https://pecan.readthedocs.io/en/latest/databases.html
        """

        DbContext.engine = DbContext._engine_from_config(sqlalchemy_conf)
        DbContext.DbSession = sessionmaker(bind=DbContext.engine)

        DbContext.metadata = base.create_tables(DbContext.engine)
        DbContext.metadata.bind = DbContext.engine

    def __init__(self, session=None):
        LOG.debug("initing DbContext ...")
        if not session:
            if not DbContext.engine:
                raise Exception("DbContext must be inited with DbContext.init_dbcontext() first")
            session = scoped_session(DbContext.DbSession)
        self.session = session

    def __del__(self):
        LOG.debug("deleting DbContext ...")
        pass

    def get_session(self):
        return self.session

    def start(self):
        pass

    def start_read_only(self):
        self.start()

    def commit(self):
        self.session.commit()

    def rollback(self):
        self.session.rollback()

    def clear(self):
        self.session.remove()
