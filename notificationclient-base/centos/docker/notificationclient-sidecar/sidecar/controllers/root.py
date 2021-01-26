#coding=utf-8

from pecan import expose, redirect, rest, route, response
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

class V1Controller(rest.RestController):

    @wsexpose(wtypes.text)
    def get(self):
        return 'v1controller'


class ocloudDaemonController(rest.RestController):

    # All supported API versions
    _versions = ['v1']

    # The default API version
    _default_version = 'v1'
    v1 = V1Controller()

    @wsexpose(wtypes.text)
    def get(self):
        return 'ocloudNotification'


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


route(RootController, 'health', HealthController())

route(RootController, 'ocloudNotifications', ocloudDaemonController())
route(RootController, 'ocloudnotifications', ocloudDaemonController())

route(V1Controller, 'PTP', PtpController())
route(V1Controller, 'ptp', PtpController())
route(V1Controller, 'subscriptions', SubscriptionsController())
