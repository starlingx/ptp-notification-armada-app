#
# Copyright (c) 2022-2024 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from pecan import expose, abort
from webob.exc import HTTPException, HTTPServerError

from datetime import datetime
import logging
import oslo_messaging

from notificationclientsdk.common.helpers import constants
from notificationclientsdk.common.helpers import subscription_helper
from notificationclientsdk.services.ptp import PtpService
from notificationclientsdk.exception import client_exception
from notificationclientsdk.common.helpers import log_helper

from sidecar.repository.notification_control import notification_control

LOG = logging.getLogger(__name__)
log_helper.config_logger(LOG)


class ResourceAddressController(object):
    def __init__(self, resource_address):
        self.resource_address = resource_address

    @expose('json')
    def CurrentState(self):
        try:
            # validate resource address
            _, nodename, resource, optional, self.resource_address = \
                subscription_helper.parse_resource_address(
                    self.resource_address)
            if nodename == constants.WILDCARD_CURRENT_NODE:
                nodename = notification_control.get_residing_nodename()
            LOG.info('Nodename to query: %s' % nodename)
            if not notification_control.in_service_nodenames(nodename):
                LOG.warning("Node {} is not available".format(nodename))
                raise client_exception.NodeNotAvailable(nodename)
            if resource not in constants.VALID_SOURCE_URI:
                LOG.warning("Resource {} is not valid".format(resource))
                raise client_exception.ResourceNotAvailable(resource, nodename)
            ptpservice = PtpService(notification_control)
            ptpstatus = ptpservice.query(nodename,
                                         self.resource_address, optional)
            LOG.info('Received ptpstatus: %s', ptpstatus)
            if isinstance(ptpstatus, dict):
                try:
                    for item in ptpstatus:
                        ptpstatus[item]['time'] = datetime.fromtimestamp(
                            ptpstatus[item]['time']).strftime(
                                '%Y-%m-%dT%H:%M:%S%fZ')
                except TypeError:
                    # ptpstatus does not have instance tags
                    ptpstatus['time'] = datetime.fromtimestamp(
                            ptpstatus['time']).strftime(
                                '%Y-%m-%dT%H:%M:%S%fZ')
            elif isinstance(ptpstatus, list):
                for item in ptpstatus:
                    item['time'] = datetime.fromtimestamp(
                        item['time']).strftime(
                            '%Y-%m-%dT%H:%M:%S%fZ')
            return ptpstatus
        except client_exception.NodeNotAvailable as ex:
            LOG.warning("{0}".format(str(ex)))
            abort(404)
        except client_exception.ResourceNotAvailable as ex:
            LOG.warning("{0}".format(str(ex)))
            abort(404)
        except oslo_messaging.exceptions.MessagingTimeout as ex:
            LOG.warning("Resource is not reachable:{0}".format(str(ex)))
            abort(404)
        except HTTPException as ex:
            LOG.warning("Client side error:{0},{1}".format(type(ex), str(ex)))
            # raise ex
            abort(400)
        except TypeError as ex:
            LOG.error("Resource {0} not found on {1}, error: {2}".format(
                self.resource_address, nodename, ex))
            abort(404)
        except HTTPServerError as ex:
            LOG.error("Server side error:{0},{1}".format(type(ex), str(ex)))
            # raise ex
            abort(500)
        except Exception as ex:
            LOG.error("Exception:{0}@{1}".format(type(ex), str(ex)))
            abort(500)
