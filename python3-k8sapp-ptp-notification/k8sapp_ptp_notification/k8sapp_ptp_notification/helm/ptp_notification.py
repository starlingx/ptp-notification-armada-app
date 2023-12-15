#
# Copyright (c) 2021 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from k8sapp_ptp_notification.common import constants as app_constants

from sysinv.common import constants

from sysinv.helm import base
from sysinv.helm import common


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
