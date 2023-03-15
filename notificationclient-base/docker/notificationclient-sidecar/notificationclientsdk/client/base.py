#
# Copyright (c) 2021 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import os
import json
import time
import threading
import oslo_messaging
from oslo_config import cfg
from notificationclientsdk.common.helpers import rpc_helper
from notificationclientsdk.model.dto.rpc_endpoint import RpcEndpointInfo

import logging

LOG = logging.getLogger(__name__)

from notificationclientsdk.common.helpers import log_helper
log_helper.config_logger(LOG)

class BrokerClientBase(object):
    def __init__(self, broker_name, broker_transport_endpoint):
        self.broker_name = broker_name
        self.listeners = {}
        self.broker_endpoint = RpcEndpointInfo(broker_transport_endpoint)
        self.transport = rpc_helper.get_transport(self.broker_endpoint)
        self._workerevent = threading.Event()
        self._workerlock = threading.Lock()
        self._workerterminated = False
        # spawn a thread to retry on setting up listener
        self._workerthread = threading.Thread(target=self._refresher, args=())
        self._workerthread.start()

        LOG.debug("Created Broker client:{0},{1}".format(broker_name, broker_transport_endpoint))

    def __del__(self):
        self.cleanup()

    def cleanup(self):
        self.clean_listeners()
        self._workerterminated = True
        if self._workerevent:
            self._workerevent.set()
        if self.transport:
            self.transport.cleanup()
            del self.transport
            self.transport = None
        return

    def _refresher(self, retry_interval=5):
        while not self._workerterminated:
            self._workerevent.wait()
            self._workerevent.clear()
            allset = False
            with self._workerlock:
                allset = self._refresh()
            if self._workerevent.is_set():
                continue
            if not allset:
                # retry later
                time.sleep(retry_interval)
                # retry on next loop
                self._workerevent.set()

    def __is_listening(self, context):
        isactive = context and context.get(
            'active', False) and context.get('rpcserver', False)
        return isactive

    def __create_listener(self, context):
        target = oslo_messaging.Target(
            topic=context['topic'],
            server=context['server'])
        endpoints = context['endpoints']
        server = oslo_messaging.get_rpc_server(
            self.transport, target, endpoints, executor=None)
        return server

    def _refresh(self):
        allset = True
        for topic, servers in self.listeners.items():
            for servername, context in servers.items():
                try:
                    rpcserver = context.get('rpcserver', None)
                    isactive = context.get('active', False)
                    if isactive and not rpcserver:
                        rpcserver = self.__create_listener(context)
                        rpcserver.start()
                        context['rpcserver'] = rpcserver
                        LOG.debug("Started rpcserver@{0}@{1}".format(context['topic'], context['server']))
                    elif not isactive and rpcserver:
                        rpcserver.stop()
                        rpcserver.wait()
                        context.pop('rpcserver')
                        LOG.debug("Stopped rpcserver@{0}@{1}".format(context['topic'], context['server']))
                except Exception as ex:
                    LOG.error("Failed to update listener for topic/server:{0}/{1}, reason:{2}"
                    .format(topic, servername, str(ex)))
                    allset = False
                    continue
        return allset

    def _trigger_refresh_listener(self):
        self._workerevent.set()
        # # sleep to re-schedule to run worker thread
        # time.sleep(2)

    def add_listener(self, topic, server, listener_endpoints=None):
        context = self.listeners.get(topic,{}).get(server, {})
        with self._workerlock:
            if not context:
                context = {
                    'endpoints': listener_endpoints,
                    'topic': topic,
                    'server': server,
                    'active': True
                    }
                if not self.listeners.get(topic, None):
                    self.listeners[topic] = {}
                self.listeners[topic][server] = context
            else:
                context['endpoints'] = listener_endpoints
                context['active'] = True

        self._trigger_refresh_listener()

    def remove_listener(self, topic, server):
        context = self.listeners.get(topic,{}).get(server, {})
        with self._workerlock:
            if context:
                context['active'] = False
        self._trigger_refresh_listener()

    def is_listening(self, topic, server):
        context = self.listeners.get(topic,{}).get(server, {})
        return self.__is_listening(context)

    def any_listener(self):
        for topic, servers in self.listeners.items():
            for servername, context in servers.items():
                if self.__is_listening(context):
                    return True
        return False

    def __is_connected(self, context):
        return context.get('rpcserver', None) is not None if context else False

    def clean_listeners(self):
        for topic, servers in self.listeners.items():
            for server, context in servers.items():
                self.remove_listener(topic, server)
                self._trigger_refresh_listener()
                LOG.debug("listener {0}@{1} {2} stopped".format(
                    topic, server,
                    'is' if self.__is_connected(context) else 'is not yet'))

    def call(self, topic, server, api_name, timeout=None, retry=None, **api_kwargs):
        target = oslo_messaging.Target(
            topic=topic, server=server, version=self.broker_endpoint.Version,
            namespace=self.broker_endpoint.Namespace)
        # note: the call might stuck here on 'Connection failed' and retry forever
        # due to the tcp connection is unreachable: 'AMQP server on <broker host>:<port> is unreachable: timed out'
        queryclient = oslo_messaging.get_rpc_client(self.transport, target, timeout = timeout, retry = retry)
        return queryclient.call({}, api_name, **api_kwargs)

    def cast(self, topic, api_name, timeout=None, retry=None, **api_kwargs):
        target = oslo_messaging.Target(
            topic=topic, fanout=True, version=self.broker_endpoint.Version,
            namespace=self.broker_endpoint.Namespace)
        queryclient = oslo_messaging.get_rpc_client(self.transport, target, timeout = timeout, retry = retry)
        queryclient.cast({}, api_name, **api_kwargs)
