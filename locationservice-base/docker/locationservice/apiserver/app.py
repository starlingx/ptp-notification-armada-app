#
# Copyright (c) 2021 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from pecan import make_app
from apiserver.repository.notification_control import notification_control

from pecan import conf

def setup_app(config):

    notification_control.refresh()
    app_conf = dict(config.app)

    return make_app(
        app_conf.pop('root'),
        logging=getattr(config, 'logging', {}),
        **app_conf
    )
