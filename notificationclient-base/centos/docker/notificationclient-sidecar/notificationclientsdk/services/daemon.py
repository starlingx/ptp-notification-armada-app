#
# Copyright (c) 2021 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import logging

import multiprocessing as mp

from notificationclientsdk.common.helpers import rpc_helper
from notificationclientsdk.model.dto.rpc_endpoint import RpcEndpointInfo
from notificationclientsdk.client.locationservice import LocationServiceClient
from notificationclientsdk.services.notification_worker import NotificationWorker

LOG = logging.getLogger(__name__)

from notificationclientsdk.common.helpers import log_helper
log_helper.config_logger(LOG)

'''Entry point of Default Process Worker'''
def ProcessWorkerDefault(event, subscription_event, daemon_context):
    worker = NotificationWorker(event, subscription_event, daemon_context)
    worker.run()
    return


class DaemonControl(object):

    def __init__(self, daemon_context, process_worker = None):
        self.daemon_context = daemon_context
        self.residing_node_name = daemon_context['THIS_NODE_NAME']
        self.event = mp.Event()
        self.subscription_event = mp.Event()
        self.registration_endpoint = RpcEndpointInfo(daemon_context['REGISTRATION_TRANSPORT_ENDPOINT'])
        self.registration_transport = rpc_helper.get_transport(self.registration_endpoint)
        self.locationservice_client = LocationServiceClient(self.registration_endpoint.TransportEndpoint)

        if not process_worker:
            process_worker = ProcessWorkerDefault

        self.mpinstance = mp.Process( target=process_worker, args=(
            self.event, self.subscription_event, daemon_context))
        self.mpinstance.start()
        # initial update
        self.refresh()
        pass

    def refresh(self):
        self.subscription_event.set()
        self.event.set()
