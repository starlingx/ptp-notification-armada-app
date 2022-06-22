#
# Copyright (c) 2021 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from notificationclientsdk.repository.dbcontext import DbContext

defaults = {
    'dbcontext': None
}

def init_default_dbcontext(sqlalchemy_conf):
    global defaults
    DbContext.init_dbcontext(sqlalchemy_conf)
    default_dbcontext = DbContext()
    defaults['dbcontext'] = default_dbcontext
    return default_dbcontext
