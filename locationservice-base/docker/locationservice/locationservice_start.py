#
# Copyright (c) 2024 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import logging
import os
import socket
from wsgiref import simple_server

from locationservicesdk.common.helpers import log_helper
from netaddr import IPAddress
from pecan.deploy import deploy

LOG = logging.getLogger(__name__)
log_helper.config_logger(LOG)

LOCATION_SERVICE_HOST = os.environ.get(
    "LOCATION_SERVICE_HOST", '127.0.0.1')
LOCATION_SERVICE_PORT = int(
    os.environ.get("LOCATION_SERVICE_PORT", '8080'))


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
        LOCATION_SERVICE_HOST)
    application = deploy('/opt/locationservice/config.py')

    with simple_server.make_server(LOCATION_SERVICE_HOST,
                                   LOCATION_SERVICE_PORT,
                                   application) as httpd:
        LOG.info("locationservice_start.py: Starting locationservice")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
