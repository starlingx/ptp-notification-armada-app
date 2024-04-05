#
# Copyright (c) 2024 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import logging
import os
import socket
from wsgiref import simple_server

from netaddr import IPAddress
from notificationclientsdk.common.helpers import log_helper
from pecan.deploy import deploy

LOG = logging.getLogger(__name__)
log_helper.config_logger(LOG)

SIDECAR_API_HOST = os.environ.get(
    "SIDECAR_API_HOST", '127.0.0.1')
SIDECAR_API_PORT = int(
    os.environ.get("SIDECAR_API_PORT", '8080'))


def get_address_family(ip_string):
    """
    Get the family for the given ip address string.
    """
    ip_address = IPAddress(ip_string)
    if ip_address.version == 6:
        return socket.AF_INET6
    else:
        return socket.AF_INET


def main():
    simple_server.WSGIServer.address_family = get_address_family(
        SIDECAR_API_HOST)
    application = deploy('/opt/notificationclient/config.py')

    with simple_server.make_server(SIDECAR_API_HOST,
                                   SIDECAR_API_PORT,
                                   application) as httpd:
        LOG.info("notificationclient_start.py: Starting notificationclient")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
