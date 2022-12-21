# Copyright (c) 2021 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
from k8sapp_ptp_notification.common import constants as app_constants
from k8sapp_ptp_notification.tests import test_plugins

from sysinv.db import api as dbapi
from sysinv.helm import common

from sysinv.tests.db import base as dbbase
from sysinv.tests.db import utils as dbutils
from sysinv.tests.helm import base


class PTPNotificationTestCase(test_plugins.K8SAppPTPNotificationAppMixin,
                          base.HelmTestCaseMixin):

    def setUp(self):
        super(PTPNotificationTestCase, self).setUp()
        self.app = dbutils.create_test_app(name='ptp-notification')
        self.dbapi = dbapi.get_instance()


class PTPNotificationIPv4ControllerHostTestCase(PTPNotificationTestCase,
                                            dbbase.ProvisionedControllerHostTestCase):

    def test_replicas(self):
        overrides = self.operator.get_helm_chart_overrides(
            app_constants.HELM_CHART_PTP_NOTIFICATION,
            cnamespace=common.HELM_NS_NOTIFICATION)

        self.assertOverridesParameters(overrides, {
            # 1 replica for 1 controller
            'replicaCount': 1
        })


class PTPNotificationIPv6AIODuplexSystemTestCase(PTPNotificationTestCase,
                                             dbbase.BaseIPv6Mixin,
                                             dbbase.ProvisionedAIODuplexSystemTestCase):

    def test_replicas(self):
        overrides = self.operator.get_helm_chart_overrides(
            app_constants.HELM_CHART_PTP_NOTIFICATION,
            cnamespace=common.HELM_NS_NOTIFICATION)

        self.assertOverridesParameters(overrides, {
            # 2 replicas for 2 controllers
            'replicaCount': 2
        })
