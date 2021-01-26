import os
import json
import time
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
        LOG.debug("Created Broker client:{0}".format(broker_name))

    def __del__(self):
        self.transport.cleanup()
        del self.transport
        return

    def __create_listener(self, context):
        target = oslo_messaging.Target(
            topic=context['topic'],
            server=context['server'])
        endpoints = context['endpoints']
        server = oslo_messaging.get_rpc_server(
            self.transport, target, endpoints, executor=None)
        return server

    def _refresh(self):
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
                except:
                    LOG.error("Failed to update listener for topic/server:{0}/{1}"
                    .format(topic, servername))
                    continue

    def add_listener(self, topic, server, listener_endpoints=None):
        context = self.listeners.get(topic,{}).get(server, {})
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

        self._refresh()

    def remove_listener(self, topic, server):
        context = self.listeners.get(topic,{}).get(server, {})
        if context:
            context['active'] = False
        self._refresh()

    def is_listening(self, topic, server):
        context = self.listeners.get(topic,{}).get(server, {})
        return context.get('active', False)

    def any_listener(self):
        for topic, servers in self.listeners.items():
            for servername, context in servers.items():
                isactive = context.get('active', False)
                if isactive:
                    return True
        return False

    def call(self, topic, server, api_name, timeout=None, retry=None, **api_kwargs):
        target = oslo_messaging.Target(
            topic=topic, server=server, version=self.broker_endpoint.Version,
            namespace=self.broker_endpoint.Namespace)
        # note: the call might stuck here on 'Connection failed' and retry forever
        # due to the tcp connection is unreachable: 'AMQP server on <broker host>:<port> is unreachable: timed out'
        queryclient = oslo_messaging.RPCClient(self.transport, target, timeout = timeout, retry = retry)
        return queryclient.call({}, api_name, **api_kwargs)

    def cast(self, topic, api_name, timeout=None, retry=None, **api_kwargs):
        target = oslo_messaging.Target(
            topic=topic, fanout=True, version=self.broker_endpoint.Version,
            namespace=self.broker_endpoint.Namespace)
        queryclient = oslo_messaging.RPCClient(self.transport, target, timeout = timeout, retry = retry)
        queryclient.cast({}, api_name, **api_kwargs)
