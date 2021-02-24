#coding=utf-8
#
# Copyright (c) 2021 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from pecan import expose, rest, abort
from webob.exc import status_map
import os

from wsme import types as wtypes
from wsmeext.pecan import wsexpose

THIS_NODE_NAME = os.environ.get("THIS_NODE_NAME",'controller-0')

from sidecar.controllers.v1.subscriptions import SubscriptionsController
from sidecar.controllers.v1.resource.ptp import PtpController

class HealthController(rest.RestController):

    @wsexpose(wtypes.text)
    def get(self):
        return {'health': True}

    @expose("json")
    def _lookup(self, primary_key, *remainder):
        abort(404)

class V1Controller(rest.RestController):

    @wsexpose(wtypes.text)
    def get(self):
        return 'v1controller'

    @expose("json")
    def _lookup(self, primary_key, *remainder):
        if primary_key:
            if 'ptp' == primary_key.lower():
                return PtpController(), remainder
            elif 'subscriptions' == primary_key.lower():
                return SubscriptionsController(), remainder
        abort(404)

class ocloudDaemonController(rest.RestController):

    # All supported API versions
    _versions = ['v1']

    # The default API version
    _default_version = 'v1'
    v1 = V1Controller()

    @wsexpose(wtypes.text)
    def get(self):
        return 'ocloudNotification'

    @expose("json")
    def _lookup(self, primary_key, *remainder):
        if primary_key:
            if 'v1' == primary_key.lower():
                return V1Controller(), remainder
        abort(404)

class RootController(object):

    @expose(generic=True, template='json')
    def index(self):
        return dict()

    @expose('json')
    def error(self, status):
        try:
            status = int(status)
        except ValueError:  # pragma: no cover
            status = 500
        message = getattr(status_map.get(status), 'explanation', '')
        return dict(status=status, message=message)

    @expose("json")
    def _lookup(self, primary_key, *remainder):
        if primary_key:
            if 'ocloudnotifications' == primary_key.lower():
                return ocloudDaemonController(), remainder
            elif 'health' == primary_key.lower():
                return HealthController(), remainder
        abort(404)
