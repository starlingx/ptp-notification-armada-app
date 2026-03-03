#!/usr/bin/env python3
#
# Copyright (c) 2021-2026 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import glob
import ipaddress
import json
import logging
import os
import re
from pathlib import Path

from trackingfunctionsdk.common.helpers import constants
from trackingfunctionsdk.services.config_watcher import ConfigFileWatcher
from trackingfunctionsdk.services.daemon import DaemonControl
from trackingfunctionsdk.services.health import HealthServer

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)


def build_endpoint(user, password, host, port):
    """Build RabbitMQ endpoint with IPv6 support"""
    try:
        ip = ipaddress.ip_address(host)
        if ip.version == 6:
            host = f"[{host}]"
    except ValueError:
        pass  # Not an IP address, use as-is
    return f"rabbit://{user}:{password}@{host}:{port}"


def get_configs(pattern, service_env_var, service_prefix):
    """Get configuration files if service is enabled"""
    if os.environ.get(service_env_var, "").lower() == "false":
        return [], []

    configs = glob.glob(pattern)
    instances = [re.search(f'{service_prefix}-(.+)\\.conf', c).group(1)
                 for c in configs]
    return configs, instances


def build_context():
    """Build daemon context from environment and config discovery"""
    # Get configurations
    ptp4l_configs, ptp4l_instances = get_configs(
        f"{constants.PTP_CONFIG_PATH}ptp4l-*.conf", "PTP4L_SERVICE_NAME", "ptp4l")

    # GNSS only if ice driver present
    gnss_configs, gnss_instances = [], []
    if Path("/ice/ice/").is_dir():
        gnss_configs, gnss_instances = get_configs(
            f"{constants.TS2PHC_CONFIG_PATH}ts2phc-*.conf", "TS2PHC_SERVICE_NAME", "ts2phc")

    # PHC2SYS
    phc2sys_configs = glob.glob(
        f"{constants.PHC2SYS_CONFIG_PATH}phc2sys-*.conf")
    phc2sys_config = phc2sys_configs[0] if phc2sys_configs else None
    if len(phc2sys_configs) > 1:
        LOG.warning("Multiple phc2sys configs found, using first one: %s",
                    phc2sys_config)
    phc2sys_service = (re.search(r'phc2sys-(.+)\.conf', phc2sys_config)
                       .group(1) if phc2sys_config else None)

    reg_endpoint = build_endpoint(
        os.environ.get('REGISTRATION_USER', 'guest'),
        os.environ.get('REGISTRATION_PASS', 'guest'),
        os.environ.get('REGISTRATION_HOST', 'localhost'),
        os.environ.get('REGISTRATION_PORT', '5672')
    )

    notif_endpoint = build_endpoint(
        os.environ.get('NOTIFICATIONSERVICE_USER', 'guest'),
        os.environ.get('NOTIFICATIONSERVICE_PASS', 'guest'),
        os.environ.get('THIS_POD_IP', '127.0.0.1'),
        os.environ.get('NOTIFICATIONSERVICE_PORT', '5672')
    )

    return {
        'THIS_NAMESPACE': os.environ.get("THIS_NAMESPACE", 'notification'),
        'THIS_NODE_NAME': os.environ.get("THIS_NODE_NAME", 'controller-0'),
        'THIS_POD_IP': os.environ.get("THIS_POD_IP", '127.0.0.1'),
        'REGISTRATION_TRANSPORT_ENDPOINT': reg_endpoint,
        'NOTIFICATION_TRANSPORT_ENDPOINT': notif_endpoint,
        'GNSS_CONFIGS': gnss_configs,
        'GNSS_INSTANCES': gnss_instances,
        'PHC2SYS_CONFIG': phc2sys_config,
        'PHC2SYS_SERVICE_NAME': phc2sys_service,
        'PTP4L_CONFIGS': ptp4l_configs,
        'PTP4L_INSTANCES': ptp4l_instances,
    }


if __name__ == "__main__":
    sqlalchemy_conf = {'url': 'sqlite:///apiserver.db', 'echo': False}
    daemon = None
    watcher = None
    health_server = None

    def on_config_change():
        """Callback when config files change"""
        if daemon:
            daemon.request_reload()

    try:
        # Start health server once for k8s httpGet health checks (shared across
        # reloads)
        health_server = HealthServer()
        health_server.run()
        LOG.info("Health server started")

        # Start config file watcher
        watcher = ConfigFileWatcher(
            constants.LINUXPTP_CONFIG_PATH,
            on_config_change,
            debounce_seconds=2
        )
        watcher.start()
        LOG.info("Config file watcher started")

        # Main reload loop
        while True:
            context = build_context()
            LOG.info(
                f"Starting PTP tracking service with "
                f"{len(context['PTP4L_INSTANCES'])} PTP4L, "
                f"{len(context['GNSS_INSTANCES'])} GNSS instances, "
                f"PHC2SYS: {context['PHC2SYS_SERVICE_NAME']}"
            )

            daemon = DaemonControl(
                json.dumps(sqlalchemy_conf),
                json.dumps(context))
            daemon.reload_requested.clear()
            daemon.refresh()

            # If we reach here, daemon exited due to reload request
            LOG.info("Daemon exited, reloading with new configuration...")

    except KeyboardInterrupt:
        LOG.info("Shutdown requested")
    finally:
        if watcher:
            watcher.stop()
