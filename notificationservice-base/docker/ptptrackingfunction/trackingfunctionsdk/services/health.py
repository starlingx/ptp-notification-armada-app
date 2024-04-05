#
# Copyright (c) 2024 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import json
import logging
import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from netaddr import IPAddress
from pecan.deploy import deploy
from trackingfunctionsdk.common.helpers import log_helper

LOG = logging.getLogger(__name__)
log_helper.config_logger(LOG)

HEALTH_API_HOST = os.environ.get(
    "HEALTH_API_HOST", '127.0.0.1')
HEALTH_SERVICE_API_PORT = int(
    os.environ.get("HEALTH_API_PORT", '8081'))


def get_address_family(ip_string):
    """
    Get the family for the given ip address string.
    """
    ip_address = IPAddress(ip_string)
    if ip_address.version == 6:
        return socket.AF_INET6
    else:
        return socket.AF_INET


class HealthRequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(self.get_response().encode("utf-8"))

    def do_POST(self):
        self.do_GET()

    def get_response(self):
        """
        Return a simple confirmation if the process is running.
        Can be extended to check broader health aspects of notification service as needed
        """
        return json.dumps(
            {'health': True}
        )


class HealthServer:
    def __init__(self):
        HTTPServer.address_family = get_address_family(HEALTH_API_HOST)
        self.health_server = HTTPServer(
            (HEALTH_API_HOST, HEALTH_SERVICE_API_PORT), HealthRequestHandler)
        self.thread = threading.Thread(target=self.health_server.serve_forever)
        self.thread.daemon = True

    def run(self):
        self.thread.start()
        return


if __name__ == "__main__":
    my_health = HealthServer()
    my_health.run()
    print(
        f"Health server running on {HEALTH_API_HOST}:{str(HEALTH_SERVICE_API_PORT)}")
    while True:
        # run indefinitely
        pass
