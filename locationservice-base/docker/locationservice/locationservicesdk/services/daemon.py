
import os
import json
import time
import oslo_messaging
from oslo_config import cfg
import logging

import multiprocessing as mp

from locationservicesdk.common.helpers import rpc_helper
from locationservicesdk.model.dto.rpc_endpoint import RpcEndpointInfo
from locationservicesdk.model.dto.resourcetype import ResourceType

from locationservicesdk.client.locationproducer import LocationProducer

LOG = logging.getLogger(__name__)

from locationservicesdk.common.helpers import log_helper
log_helper.config_logger(LOG)

'''Entry point of Default Process Worker'''
def ProcessWorkerDefault(event, sqlalchemy_conf_json, registration_endpoint, location_info_json):
    worker = LocationWatcherDefault(event, sqlalchemy_conf_json, registration_endpoint, location_info_json)
    worker.run()
    return


class LocationWatcherDefault:
    class LocationRequestHandlerDefault(object):
        def __init__(self, watcher):
            self.watcher = watcher

        def handle(self, **rpc_kwargs):
            self.watcher.signal_location_event()

    def __init__(self, event, sqlalchemy_conf_json, registration_transport_endpoint, location_info_json):
        self.sqlalchemy_conf = json.loads(sqlalchemy_conf_json)
        self.event = event
        self.event_timeout = float(2.0)
        self.event_iteration = 0
        self.location_info = json.loads(location_info_json)
        this_node_name = self.location_info['NodeName']

        self.registration_endpoint = RpcEndpointInfo(registration_transport_endpoint)
        self.LocationProducer = LocationProducer(
            this_node_name,
            self.registration_endpoint.TransportEndpoint)

    def signal_location_event(self):
        if self.event:
            self.event.set()
        else:
            LOG.warning("Unable to assert location event")
            pass

    def run(self):
        # start location listener
        self.__start_listener()
        while True:
            # annouce the location
            self.__announce_location()
            if self.event.wait(self.event_timeout):
                LOG.debug("daemon control event is asserted")
                self.event.clear()
            else:
                # max timeout: 1 hour
                if self.event_timeout < float(3600):
                    self.event_timeout = self.event_timeout + self.event_timeout
                LOG.debug("daemon control event is timeout")
            continue
        self.__stop_listener()

    '''Start listener to answer querying from clients'''
    def __start_listener(self):
        LOG.debug("start listener to answer location querying")

        self.LocationProducer.start_location_listener(
            self.location_info,
            LocationWatcherDefault.LocationRequestHandlerDefault(self)
            )
        return

    def __stop_listener(self):
        LOG.debug("stop listener to answer location querying")

        self.LocationProducer.stop_location_listener(self.location_info)
        return

    '''announce location'''
    def __announce_location(self):
        LOG.debug("announce location info to clients")
        self.LocationProducer.announce_location(self.location_info)
        return

class DaemonControl(object):

    def __init__(
        self, sqlalchemy_conf_json, registration_transport_endpoint,
        location_info, process_worker = None, daemon_mode=True):

        self.daemon_mode = daemon_mode
        self.event = mp.Event()
        self.registration_endpoint = RpcEndpointInfo(registration_transport_endpoint)
        self.registration_transport = rpc_helper.get_transport(self.registration_endpoint)
        self.location_info = location_info
        self.sqlalchemy_conf_json = sqlalchemy_conf_json

        if not process_worker:
            process_worker = ProcessWorkerDefault
        self.process_worker = process_worker

        if not self.daemon_mode:
            return

        self.mpinstance = mp.Process(
            target=process_worker,
            args=(self.event, self.sqlalchemy_conf_json,
            self.registration_endpoint.TransportEndpoint,
            self.location_info))
        self.mpinstance.start()

        pass

    def refresh(self):
        if not self.daemon_mode:
            self.process_worker(
                self.event, self.sqlalchemy_conf_json,
                self.registration_endpoint.TransportEndpoint, self.location_info)

        self.event.set()
