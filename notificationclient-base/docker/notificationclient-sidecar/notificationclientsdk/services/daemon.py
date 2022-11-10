#
# Copyright (c) 2021 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import logging

import multiprocessing as mp

from notificationclientsdk.common.helpers import rpc_helper
from notificationclientsdk.common.helpers import log_helper
from notificationclientsdk.model.dto.rpc_endpoint import RpcEndpointInfo
from notificationclientsdk.client.locationservice import LocationServiceClient
from notificationclientsdk.services.notification_worker import \
    NotificationWorker

LOG = logging.getLogger(__name__)
log_helper.config_logger(LOG)


def ProcessWorkerDefault(event,
                         subscription_event,
                         daemon_context,
                         service_nodenames):
    '''Entry point of Default Process Worker'''
    worker = NotificationWorker(event,
                                subscription_event,
                                daemon_context,
                                service_nodenames)
    worker.run()


class DaemonControl(object):
    def __init__(self, daemon_context, process_worker=None):
        self.daemon_context = daemon_context
        self.residing_node_name = daemon_context['THIS_NODE_NAME']
        self.event = mp.Event()
        self.subscription_event = mp.Event()
        self.manager = mp.Manager()
        self.service_nodenames = self.manager.list()
        LOG.debug('Managed (shared) list of nodes id %d contents %s' %
                  (id(self.service_nodenames), self.service_nodenames))
        self.registration_endpoint = RpcEndpointInfo(
            daemon_context['REGISTRATION_TRANSPORT_ENDPOINT'])
        self.registration_transport = rpc_helper.get_transport(
            self.registration_endpoint)
        self.locationservice_client = LocationServiceClient(
            self.registration_endpoint.TransportEndpoint)

        if not process_worker:
            process_worker = ProcessWorkerDefault

        self.mpinstance = mp.Process(target=process_worker,
                                     args=(self.event,
                                           self.subscription_event,
                                           daemon_context,
                                           self.service_nodenames))
        self.mpinstance.start()

        # initial update
        self.refresh()

    def __del__(self):
        if self.locationservice_client:
            self.locationservice_client.cleanup()
            self.locationservice_client = None

    def refresh(self):
        self.subscription_event.set()
        self.event.set()

    def get_residing_nodename(self):
        return self.residing_node_name

    def in_service_nodenames(self, nodename):
        return nodename in self.service_nodenames

    def list_of_service_nodenames(self):
        return self.service_nodenames[:]
