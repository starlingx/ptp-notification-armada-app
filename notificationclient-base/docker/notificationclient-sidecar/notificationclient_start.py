#
# Copyright (c) 2024, 2026 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import logging
from notificationclientsdk.common.helpers import log_helper
import os
from pecan.deploy import deploy
from waitress import serve

LOG = logging.getLogger(__name__)
log_helper.config_logger(LOG)

SIDECAR_API_HOST = os.environ.get(
    "SIDECAR_API_HOST", '127.0.0.1')
SIDECAR_API_PORT = int(
    os.environ.get("SIDECAR_API_PORT", '8080'))


def main():
    application = deploy('/opt/notificationclient/config.py')
    LOG.info("notificationclient_start.py: Starting notificationclient")
    serve(application, host=SIDECAR_API_HOST, port=SIDECAR_API_PORT)


if __name__ == "__main__":
    main()
