#coding=utf-8

from pecan import expose, redirect, rest, route, response, abort
from webob.exc import HTTPException, HTTPNotFound, HTTPBadRequest, HTTPClientError, HTTPServerError

from wsme import types as wtypes
from wsmeext.pecan import wsexpose

import os
import logging
import oslo_messaging

from notificationclientsdk.services.ptp import PtpService
from notificationclientsdk.exception import client_exception

from sidecar.repository.notification_control import notification_control

LOG = logging.getLogger(__name__)

from notificationclientsdk.common.helpers import log_helper
log_helper.config_logger(LOG)

THIS_NODE_NAME = os.environ.get("THIS_NODE_NAME",'controller-0')

class CurrentStateController(rest.RestController):
    def __init__(self):
        pass

    @expose('json')
    def get(self):
        try:
            ptpservice = PtpService(notification_control)
            ptpstatus = ptpservice.query(THIS_NODE_NAME)
            # response.status = 200
            return ptpstatus
        except client_exception.NodeNotAvailable as ex:
            LOG.warning("Node is not available:{0}".format(str(ex)))
            abort(404)
        except client_exception.ResourceNotAvailable as ex:
            LOG.warning("Resource is not available:{0}".format(str(ex)))
            abort(404)
        except oslo_messaging.exceptions.MessagingTimeout as ex:
            LOG.warning("Resource is not reachable:{0}".format(str(ex)))
            abort(404)
        except HTTPException as ex:
            LOG.warning("Client side error:{0},{1}".format(type(ex), str(ex)))
            # raise ex
            abort(400)
        except HTTPServerError as ex:
            LOG.error("Server side error:{0},{1}".format(type(ex), str(ex)))
            # raise ex
            abort(500)
        except Exception as ex:
            LOG.error("Exception:{0}@{1}".format(type(ex),str(ex)))
            abort(500)

class PtpController(rest.RestController):
    def __init__(self):
        pass

    @wsexpose(wtypes.text)
    def get(self):
        return 'ptp'

route(PtpController, 'CurrentState', CurrentStateController())
route(PtpController, 'currentstate', CurrentStateController())
