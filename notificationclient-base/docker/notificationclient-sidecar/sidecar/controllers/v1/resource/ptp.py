#
# Copyright (c) 2020-2022 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from pecan import expose, rest, route, abort
from webob.exc import HTTPException, HTTPServerError

from wsme import types as wtypes
from wsmeext.pecan import wsexpose

import logging
import oslo_messaging

from notificationclientsdk.common.helpers import log_helper
from notificationclientsdk.services.ptp import PtpService
from notificationclientsdk.exception import client_exception

from sidecar.repository.notification_control import notification_control

LOG = logging.getLogger(__name__)
log_helper.config_logger(LOG)


class CurrentStateController(rest.RestController):
    def __init__(self):
        pass

    @expose('json')
    def get(self):
        try:
            ptpservice = PtpService(notification_control)
            service_node_name = notification_control.get_service_nodename()
            LOG.debug('service_node_name is %s' % service_node_name)
            ptpstatus = ptpservice.query(service_node_name)
            LOG.debug('Got ptpstatus: %s' % ptpstatus)
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
            LOG.error("Exception:{0}@{1}".format(type(ex), str(ex)))
            abort(500)


class PtpController(rest.RestController):
    def __init__(self):
        pass

    @wsexpose(wtypes.text)
    def get(self):
        return 'ptp'


route(PtpController, 'CurrentState', CurrentStateController())
route(PtpController, 'currentstate', CurrentStateController())
