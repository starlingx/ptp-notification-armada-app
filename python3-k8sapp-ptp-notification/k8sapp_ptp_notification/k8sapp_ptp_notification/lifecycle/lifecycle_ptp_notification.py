#
# Copyright (c) 2025 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
# All Rights Reserved.
#

""" System inventory App lifecycle operator."""

from k8sapp_ptp_notification.common import constants as app_constants
from oslo_log import log as logging
from sysinv.common import constants
from sysinv.common import exception
from sysinv.common import kubernetes
from sysinv.common import utils as cutils
from sysinv.helm import lifecycle_base as base
from sysinv.helm.lifecycle_constants import LifecycleConstants

LOG = logging.getLogger(__name__)


class PtpNotificationAppLifecycleOperator(base.AppLifecycleOperator):
    def app_lifecycle_actions(self, context, conductor_obj, app_op, app, hook_info):
        """Perform lifecycle actions for an operation

        :param context: request context, can be None
        :param conductor_obj: conductor object, can be None
        :param app_op: AppOperator object
        :param app: AppOperator.Application object
        :param hook_info: LifecycleHookInfo object

        """
        if hook_info.lifecycle_type == LifecycleConstants.APP_LIFECYCLE_TYPE_FLUXCD_REQUEST:
            if hook_info.operation == constants.APP_APPLY_OP:
                if hook_info.relative_timing == LifecycleConstants.APP_LIFECYCLE_TIMING_POST:
                    return self.post_apply(app)

        if hook_info.lifecycle_type == LifecycleConstants.APP_LIFECYCLE_TYPE_OPERATION:
            if hook_info.operation == constants.APP_REMOVE_OP:
                if hook_info.relative_timing == LifecycleConstants.APP_LIFECYCLE_TIMING_PRE:
                    return self.pre_remove(app)

        if hook_info.lifecycle_type == LifecycleConstants.APP_LIFECYCLE_TYPE_OPERATION:
            if hook_info.operation == constants.APP_REMOVE_OP:
                if hook_info.relative_timing == LifecycleConstants.APP_LIFECYCLE_TIMING_POST:
                    return self.post_remove(app)

        super(PtpNotificationAppLifecycleOperator, self).app_lifecycle_actions(
            context, conductor_obj, app_op, app, hook_info
        )

    def post_apply(self, app):
        """Post apply lifecycle actions

        Args:
            app (AppOperator): Object
        """
        LOG.debug(
            "Executing post_apply for {} app".format(app_constants.HELM_APP_PTP_NOTIFICATION)
        )
        LOG.debug("{} app: post_apply".format(app.name))

    def pre_remove(self, app):
        LOG.debug(
            "Executing pre_remove for {} app".format(app_constants.HELM_APP_PTP_NOTIFICATION)
        )
        LOG.debug("{} app: pre_remove".format(app.name))

    def post_remove(self, app):
        LOG.debug(
            "Executing post_remove for {} app".format(app_constants.HELM_APP_PTP_NOTIFICATION)
        )
        cmd = ['kubectl', '--kubeconfig', kubernetes.KUBERNETES_ADMIN_CONF,
               'delete', 'namespace', app_constants.HELM_CHART_NS_NOTIFICATION]
        stdout, stderr = cutils.trycmd(*cmd)
        LOG.debug("{} app: cmd={} stdout={} stderr={}".format(app.name, cmd, stdout, stderr))

    def _get_helm_user_overrides(self, dbapi_instance, db_app_id):
        try:
            overrides = dbapi_instance.helm_override_get(
                app_id=db_app_id,
                name=app_constants.HELM_CHART_PTP_NOTIFICATION,
                namespace=app_constants.HELM_CHART_NS_NOTIFICATION,
            )
        except exception.HelmOverrideNotFound:
            values = {
                "name": app_constants.HELM_CHART_PTP_NOTIFICATION,
                "namespace": app_constants.HELM_CHART_NS_NOTIFICATION,
                "db_app_id": db_app_id,
            }
            overrides = dbapi_instance.helm_override_create(values=values)
        return overrides.user_overrides or ""
