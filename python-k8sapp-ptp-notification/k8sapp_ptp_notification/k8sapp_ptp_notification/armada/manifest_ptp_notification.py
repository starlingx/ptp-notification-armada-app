#
# Copyright (c) 2021 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
# All Rights Reserved.
#

""" System inventory Armada manifest operator."""

from k8sapp_ptp_notification.helm.rbd_provisioner import PTPNotificationHelm
from k8sapp_ptp_notification.helm.psp_rolebinding import PSPRolebindingHelm

from sysinv.common import constants
from sysinv.helm import manifest_base as base


class PTPNotificationArmadaManifestOperator(base.ArmadaManifestOperator):

    APP = constants.HELM_APP_PTP_NOTIFICATION
    ARMADA_MANIFEST = 'armada-manifest'

    CHART_GROUP_PSP_ROLEBINDING = 'ptp-notification-psp-rolebinding'
    CHART_GROUP_PTP_NOTIFICATION = 'ptp-notification'
    CHART_GROUPS_LUT = {
        PSPRolebindingHelm.CHART: CHART_GROUP_PSP_ROLEBINDING,
        PTPNotificationHelm.CHART: CHART_GROUP_PTP_NOTIFICATION
    }

    CHARTS_LUT = {
        PSPRolebindingHelm.CHART: 'ptp-notification-psp-rolebinding',
        PTPNotification.CHART: 'ptp-notification'
    }

    def platform_mode_manifest_updates(self, dbapi, mode):
        """ Update the application manifest based on the platform

        :param dbapi: DB api object
        :param mode: mode to control how to apply the application manifest
        """
        pass
