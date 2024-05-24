#
# Copyright (c) 2021-2024 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from k8sapp_ptp_notification.common import constants as app_constants

from oslo_log import log as logging

from sysinv.common import constants
from sysinv.common import exception

from sysinv.helm import base
from sysinv.helm import common

LOG = logging.getLogger(__name__)


class PTPNotificationHelm(base.BaseHelm):
    """Class to encapsulate helm operations for the ptp notification chart"""

    SUPPORTED_NAMESPACES = base.BaseHelm.SUPPORTED_NAMESPACES + \
        [common.HELM_NS_NOTIFICATION]
    SUPPORTED_APP_NAMESPACES = {
        constants.HELM_APP_PTP_NOTIFICATION:
            base.BaseHelm.SUPPORTED_NAMESPACES + [common.HELM_NS_NOTIFICATION],
    }

    CHART = app_constants.HELM_CHART_PTP_NOTIFICATION

    SERVICE_NAME = 'ptp-notification'

    def get_namespaces(self):
        return self.SUPPORTED_NAMESPACES

    def get_overrides(self, namespace=None):
        overrides = {
            app_constants.HELM_CHART_NS_NOTIFICATION: {}
        }

        if namespace in self.SUPPORTED_NAMESPACES:
            return overrides[namespace]
        elif namespace:
            raise exception.InvalidHelmNamespace(chart=self.CHART,
                                                 namespace=namespace)
        else:
            return overrides
