#
# Copyright (c) 2021-2022 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from pecan import conf
from pecan import expose, rest, response, abort
from webob.exc import HTTPException, HTTPServerError

import logging

from wsmeext.pecan import wsexpose

from notificationclientsdk.model.dto.subscription import SubscriptionInfoV2

from notificationclientsdk.repository.subscription_repo import SubscriptionRepo
from notificationclientsdk.services.ptp import PtpService
from notificationclientsdk.exception import client_exception
from notificationclientsdk.common.helpers import log_helper

from sidecar.repository.notification_control import notification_control
from sidecar.repository.dbcontext_default import defaults

LOG = logging.getLogger(__name__)
log_helper.config_logger(LOG)


class SubscriptionsControllerV2(rest.RestController):

    @wsexpose(SubscriptionInfoV2, body=SubscriptionInfoV2, status_code=201)
    def post(self, subscription):
        # decode the request body
        try:
            if subscription.ResourceAddress:
                LOG.info('subscribe: ResourceAddress {0} with '
                         'callback uri {1}'.format(
                            subscription.ResourceAddress,
                            subscription.EndpointUri))

            if not self._validateV2(subscription):
                LOG.warning('Invalid Request data:{0}'.format(
                    subscription.to_dict()))
                abort(400)

            subscription.UriLocation = \
                "{0}://{1}:{2}/ocloudNotifications/v2/subscriptions".format(
                    conf.server.get('protocol', 'http'),
                    conf.server.get('host', '127.0.0.1'),
                    conf.server.get('port', '8080')
                )
            if subscription.ResourceAddress:
                ptpservice = PtpService(notification_control)

                entry = ptpservice.add_subscription(subscription)
                subscription.SubscriptionId = entry.SubscriptionId
                subscription.UriLocation = entry.UriLocation
                LOG.info('created subscription: {0}'.format(
                    subscription.to_dict()))

                del ptpservice

            return subscription
        except client_exception.ServiceError as err:
            abort(int(str(err)))
        except client_exception.InvalidSubscription:
            abort(400)
        except client_exception.InvalidEndpoint:
            abort(400)
        except client_exception.NodeNotAvailable:
            abort(404)
        except client_exception.ResourceNotAvailable:
            abort(404)
        except HTTPException as ex:
            LOG.warning("Client side error:{0},{1}".format(type(ex), str(ex)))
            abort(400)
        except HTTPServerError as ex:
            LOG.error("Server side error:{0},{1}".format(type(ex), str(ex)))
            abort(500)
        except Exception as ex:
            LOG.error("Exception:{0}@{1}".format(type(ex), str(ex)))
            abort(500)

    @expose('json')
    def get(self):
        try:
            repo = SubscriptionRepo(defaults['dbcontext'].get_session(),
                                    autocommit=False)
            entries = repo.get(Status=1)
            response.status = 200
            subs = []
            for x in entries:
                if x.Status == 1:
                    if getattr(x, 'ResourceAddress', None) is not None:
                        subs.append(SubscriptionInfoV2(x).to_dict())
            return subs
        except HTTPException as ex:
            LOG.warning("Client side error:{0},{1}".format(type(ex), str(ex)))
            raise ex
        except HTTPServerError as ex:
            LOG.error("Server side error:{0},{1}".format(type(ex), str(ex)))
            raise ex
        except Exception as ex:
            LOG.error("Exception:{0}@{1}".format(type(ex), str(ex)))
            abort(500)

    @expose()
    def _lookup(self, subscription_id, *remainder):
        return SubscriptionController(subscription_id), remainder

    def _validateV2(self, subscription_request):
        try:
            assert subscription_request.ResourceAddress
            assert subscription_request.EndpointUri
            return True
        except Exception:
            return False


class SubscriptionController(rest.RestController):
    def __init__(self, subscription_id):
        self.subscription_id = subscription_id

    @expose('json')
    def get(self):
        try:
            repo = SubscriptionRepo(defaults['dbcontext'].get_session(),
                                    autocommit=False)
            entry = repo.get_one(SubscriptionId=self.subscription_id, Status=1)

            if not entry:
                abort(404)
            else:
                response.status = 200
                if getattr(entry, 'ResourceAddress', None):
                    return SubscriptionInfoV2(entry).to_dict()

        except HTTPException as ex:
            LOG.warning("Client side error:{0},{1}".format(type(ex), str(ex)))
            raise ex
        except HTTPServerError as ex:
            LOG.error("Server side error:{0},{1}".format(type(ex), str(ex)))
            raise ex
        except Exception as ex:
            LOG.error("Exception:{0}@{1}".format(type(ex), str(ex)))
            abort(500)

    @wsexpose(status_code=204)
    def delete(self):
        try:
            repo = SubscriptionRepo(defaults['dbcontext'].get_session(),
                                    autocommit=False)
            entry = repo.get_one(SubscriptionId=self.subscription_id)
            if entry:
                if entry.SubscriptionId:
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
            LOG.error("Exception:{0}@{1}".format(type(ex), str(ex)))
            abort(500)
