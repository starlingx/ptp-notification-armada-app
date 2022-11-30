#
# Copyright (c) 2021-2022 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from pecan import expose, rest, abort, request
from webob.exc import status_map
import os

from wsme import types as wtypes
from wsmeext.pecan import wsexpose

THIS_NODE_NAME = os.environ.get("THIS_NODE_NAME",'controller-0')

from sidecar.controllers.v1.subscriptions import SubscriptionsControllerV1
from sidecar.controllers.v2.subscriptions import SubscriptionsControllerV2
from sidecar.controllers.v1.resource.ptp import PtpController
from sidecar.controllers.v2.resource_address import ResourceAddressController
import logging
LOG = logging.getLogger(__name__)
from notificationclientsdk.common.helpers import log_helper
log_helper.config_logger(LOG)

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
                return SubscriptionsControllerV1(), remainder
        abort(404)

class V2Controller(rest.RestController):

    @wsexpose(wtypes.text)
    def get(self):
        return 'v2controller'

    @expose("json")
    def _lookup(self, primary_key, *remainder):
        if primary_key:
            if 'subscriptions' == primary_key.lower():
                return SubscriptionsControllerV2(), remainder
            elif remainder:
                if 'currentstate' == remainder[-1].lower():
                    resource_address_array = remainder[:-1]
                    resource_address = '/' + primary_key + '/' + '/'.join(resource_address_array)
                    remainder = remainder[-1:]
                    return ResourceAddressController(resource_address), remainder
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
            elif 'v2' == primary_key.lower():
                return V2Controller(), remainder
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
