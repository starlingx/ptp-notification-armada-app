#
# Copyright (c) 2021 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from sysinv.common import constants
from sysinv.tests.db import base as dbbase
from sysinv.tests.helm.test_helm import HelmOperatorTestSuiteMixin


class K8SAppPTPNotificationAppMixin(object):
    app_name = constants.HELM_APP_PTP_NOTIFICATION
    path_name = app_name + '.tgz'

    def setUp(self):
        super(K8SAppPTPNotificationAppMixin, self).setUp()


# Test Configuration:
# - Controller
# - IPv6
# - Ceph Storage
# - ptp-notification app
class K8sAppPTPNotificationControllerTestCase(K8SAppPTPNotificationAppMixin,
                                      dbbase.BaseIPv6Mixin,
                                      dbbase.BaseCephStorageBackendMixin,
                                      HelmOperatorTestSuiteMixin,
                                      dbbase.ControllerHostTestCase):
    pass


# Test Configuration:
# - AIO
# - IPv4
# - Ceph Storage
# - ptp-notification app
class K8SAppPTPNotificationAIOTestCase(K8SAppPTPNotificationAppMixin,
                               dbbase.BaseCephStorageBackendMixin,
                               HelmOperatorTestSuiteMixin,
                               dbbase.AIOSimplexHostTestCase):
    pass
