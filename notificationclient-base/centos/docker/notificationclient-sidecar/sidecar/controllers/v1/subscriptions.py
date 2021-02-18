#coding=utf-8
from pecan import conf
from pecan import expose, rest, response, abort
from webob.exc import HTTPException, HTTPNotFound, HTTPBadRequest, HTTPClientError, HTTPServerError

import os
import logging

from wsme import types as wtypes
from wsmeext.pecan import wsexpose

from notificationclientsdk.model.dto.resourcetype import ResourceType
from notificationclientsdk.model.dto.subscription import SubscriptionInfo

from notificationclientsdk.repository.subscription_repo import SubscriptionRepo
from notificationclientsdk.services.ptp import PtpService
from notificationclientsdk.exception import client_exception

from sidecar.repository.notification_control import notification_control
from sidecar.repository.dbcontext_default import defaults

LOG = logging.getLogger(__name__)

from notificationclientsdk.common.helpers import log_helper
log_helper.config_logger(LOG)

THIS_NODE_NAME = os.environ.get("THIS_NODE_NAME",'controller-0')

class SubscriptionsController(rest.RestController):
    @wsexpose(SubscriptionInfo, body=SubscriptionInfo, status_code=201)
    def post(self, subscription):
        # decode the request body
        try:
            if subscription.ResourceType == ResourceType.TypePTP:
                LOG.info(' subscribe: {0}, {1} with callback uri {2}'.format(
                    subscription.ResourceType,
                    subscription.ResourceQualifier.NodeName,
                    subscription.EndpointUri))
            else:
                LOG.warning(' Subscribe with unsupported ResourceType:{0}'.format(
                    subscription.ResourceType))
                abort(404)

            if not self._validate(subscription):
                LOG.warning(' Invalid Request data:{0}'.format(subscription.to_dict()))
                abort(400)

            subscription.UriLocation = "{0}://{1}:{2}/ocloudNotifications/v1/subscriptions".format(
                conf.server.get('protocol','http'),
                conf.server.get('host', '127.0.01'),
                conf.server.get('port', '8080')
            )
            if subscription.ResourceType == ResourceType.TypePTP:
                ptpservice = PtpService(notification_control)
                entry = ptpservice.add_subscription(subscription)
                del ptpservice
                if not entry:
                    abort(404)

            subscription.SubscriptionId = entry.SubscriptionId
            subscription.UriLocation = entry.UriLocation
            LOG.info('created subscription: {0}'.format(subscription.to_dict()))

            return subscription
        except client_exception.InvalidSubscription as ex:
            abort(400)
        except client_exception.InvalidEndpoint as ex:
            abort(400)
        except client_exception.NodeNotAvailable as ex:
            abort(404)
        except client_exception.ResourceNotAvailable as ex:
            abort(404)
        except HTTPException as ex:
            LOG.warning("Client side error:{0},{1}".format(type(ex), str(ex)))
            abort(400)
        except HTTPServerError as ex:
            LOG.error("Server side error:{0},{1}".format(type(ex), str(ex)))
            abort(500)
        except Exception as ex:
            LOG.error("Exception:{0}@{1}".format(type(ex),str(ex)))
            abort(500)

    @expose('json')
    def get(self):
        try:
            repo = SubscriptionRepo(defaults['dbcontext'].get_session(), autocommit = False)
            entries = repo.get(Status=1)

            response.status = 200
            return [SubscriptionInfo(x).to_dict() for x in entries if x.Status == 1]
        except HTTPException as ex:
            LOG.warning("Client side error:{0},{1}".format(type(ex), str(ex)))
            raise ex
        except HTTPServerError as ex:
            LOG.error("Server side error:{0},{1}".format(type(ex), str(ex)))
            raise ex
        except Exception as ex:
            LOG.error("Exception:{0}@{1}".format(type(ex),str(ex)))
            abort(500)

    @expose()
    def _lookup(self, subscription_id, *remainder):
        return SubscriptionController(subscription_id), remainder

    def _validate(self, subscription_request):
        try:
            assert subscription_request.ResourceType == 'PTP'
            assert subscription_request.EndpointUri

            return True
        except:
            return False

class SubscriptionController(rest.RestController):
    def __init__(self, subscription_id):
        self.subscription_id = subscription_id

    @expose('json')
    def get(self):
        try:
            repo = SubscriptionRepo(defaults['dbcontext'].get_session(), autocommit = False)
            entry = repo.get_one(SubscriptionId=self.subscription_id, Status=1)

            if not entry:
                abort(404)
            else:
                response.status = 200
                return SubscriptionInfo(entry).to_dict()
        except HTTPException as ex:
            LOG.warning("Client side error:{0},{1}".format(type(ex), str(ex)))
            raise ex
        except HTTPServerError as ex:
            LOG.error("Server side error:{0},{1}".format(type(ex), str(ex)))
            raise ex
        except Exception as ex:
            LOG.error("Exception:{0}@{1}".format(type(ex),str(ex)))
            abort(500)

    @wsexpose(status_code=204)
    def delete(self):
        try:
            repo = SubscriptionRepo(defaults['dbcontext'].get_session(), autocommit = False)
            entry = repo.get_one(SubscriptionId=self.subscription_id)
            if entry:
                if entry.ResourceType == ResourceType.TypePTP:
                    ptpservice = PtpService(notification_control)
                    ptpservice.remove_subscription(entry.SubscriptionId)
                    del ptpservice
                    return
                else:
                    repo.delete_one(SubscriptionId=self.subscription_id)
                    return
            abort(404)
        except HTTPException as ex:
            LOG.warning("Client side error:{0},{1}".format(type(ex), str(ex)))
            raise ex
        except HTTPServerError as ex:
            LOG.error("Server side error:{0},{1}".format(type(ex), str(ex)))
            raise ex
        except Exception as ex:
            LOG.error("Exception:{0}@{1}".format(type(ex),str(ex)))
            abort(500)
