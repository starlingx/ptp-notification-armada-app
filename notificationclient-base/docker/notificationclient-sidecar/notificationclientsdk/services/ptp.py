#
# Copyright (c) 2021-2022 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import oslo_messaging
import logging
import json
import kombu
from datetime import datetime

from notificationclientsdk.client.notificationservice \
    import NotificationServiceClient
from notificationclientsdk.common.helpers import subscription_helper
from notificationclientsdk.common.helpers import log_helper
from notificationclientsdk.common.helpers import constants
from notificationclientsdk.common.helpers.nodeinfo_helper import NodeInfoHelper
from notificationclientsdk.model.dto.resourcetype import ResourceType
from notificationclientsdk.model.dto.subscription import SubscriptionInfoV1
from notificationclientsdk.model.dto.subscription import SubscriptionInfoV2
from notificationclientsdk.model.orm.subscription \
    import Subscription as SubscriptionOrm
from notificationclientsdk.repository.node_repo import NodeRepo
from notificationclientsdk.repository.subscription_repo import SubscriptionRepo
from notificationclientsdk.exception import client_exception

LOG = logging.getLogger(__name__)
log_helper.config_logger(LOG)


class PtpService(object):

    def __init__(self, daemon_control):
        self.daemon_control = daemon_control
        self.locationservice_client = daemon_control.locationservice_client
        self.subscription_repo = SubscriptionRepo(autocommit=False)

    def __del__(self):
        del self.subscription_repo
        self.locationservice_client = None

    def __query_locationinfo(self, broker_name, timeout=5, retry=2):
        try:
            location_info = \
                self.locationservice_client.query_location(broker_name,
                                                           timeout, retry)
            LOG.debug("Pulled location info@{0}:{1}".format(
                broker_name, location_info))
            return location_info
        except Exception as ex:
            LOG.warning("Failed to query location of node:{0} "
                        "due to: {1}".format(broker_name, str(ex)))
            raise client_exception.NodeNotAvailable(broker_name)

    def __get_node_info(self, default_node_name, timeout=5, retry=2):
        try:
            nodeinfo_repo = NodeRepo(autocommit=False)
            nodeinfo = nodeinfo_repo.get_one(Status=1,
                                             NodeName=default_node_name)
            broker_pod_ip = None
            supported_resource_types = []

            if nodeinfo:
                broker_pod_ip = nodeinfo.PodIP
                supported_resource_types = json.loads(
                    nodeinfo.ResourceTypes or '[]')

            if not broker_pod_ip:
                # try to query the broker ip
                location_info = self.__query_locationinfo(
                    default_node_name, timeout, retry)
                broker_pod_ip = location_info.get("PodIP", None)
                supported_resource_types = location_info.get(
                    "ResourceTypes", [])

            return broker_pod_ip, supported_resource_types
        finally:
            del nodeinfo_repo

    def query(self, broker_name, resource_address=None, optional=None):
        default_node_name = NodeInfoHelper.default_node_name(broker_name)
        broker_pod_ip, supported_resource_types = self.__get_node_info(
            default_node_name)

        if not broker_pod_ip:
            LOG.warning("Node {0} is not available yet".format(
                default_node_name))
            raise client_exception.NodeNotAvailable(broker_name)

        if ResourceType.TypePTP not in supported_resource_types:
            LOG.warning("Resource {0}@{1} is not available yet".format(
                ResourceType.TypePTP, default_node_name))
            raise client_exception.ResourceNotAvailable(broker_name,
                                                        ResourceType.TypePTP)

        return self._query(default_node_name, broker_pod_ip,
                           resource_address, optional)

    def _query(self, broker_name, broker_pod_ip, resource_address=None,
               optional=None):
        broker_host = "[{0}]".format(broker_pod_ip)
        broker_transport_endpoint = "rabbit://{0}:{1}@{2}:{3}".format(
            self.daemon_control.daemon_context['NOTIFICATION_BROKER_USER'],
            self.daemon_control.daemon_context['NOTIFICATION_BROKER_PASS'],
            broker_host,
            self.daemon_control.daemon_context['NOTIFICATION_BROKER_PORT'])
        notificationservice_client = None
        try:
            notificationservice_client = NotificationServiceClient(
                broker_name, broker_transport_endpoint, broker_pod_ip)
            resource_status = notificationservice_client.query_resource_status(
                ResourceType.TypePTP, timeout=5, retry=10,
                resource_address=resource_address, optional=optional)
            return resource_status
        except oslo_messaging.exceptions.MessagingTimeout as ex:
            LOG.warning("ptp status is not available "
                        "@node {0} due to {1}".format(broker_name, str(ex)))
            raise client_exception.ResourceNotAvailable(broker_name,
                                                        ResourceType.TypePTP)
        except kombu.exceptions.OperationalError:
            LOG.warning("Node {0} is unreachable yet".format(broker_name))
            raise client_exception.NodeNotAvailable(broker_name)
        finally:
            if notificationservice_client:
                notificationservice_client.cleanup()
                del notificationservice_client

    def add_subscription(self, subscription_dto):
        resource_address = None
        if hasattr(subscription_dto, 'ResourceAddress'):
            version = 2
            _, nodename, _, _, _ = subscription_helper.parse_resource_address(
                subscription_dto.ResourceAddress)
            LOG.debug("nodename in ResourceAddress is '%s', residing is %s" %
                      (nodename, self.daemon_control.get_residing_nodename()))

            resource_address = subscription_dto.ResourceAddress
            LOG.debug('Looking for existing subscription for EndpointUri %s '
                      'ResourceAddress %s' % (subscription_dto.EndpointUri,
                                              resource_address))
            entry = self.subscription_repo.get_one(
                EndpointUri=subscription_dto.EndpointUri,
                ResourceAddress=resource_address)

            if entry is None:
                # Did not find matched duplicated, but needs to look for other
                # cases...
                if nodename != constants.WILDCARD_ALL_NODES:
                    # There may be a subscription for all nodes already in
                    # place
                    resource_address_star = \
                        subscription_helper.set_nodename_in_resource_address(
                            resource_address, constants.WILDCARD_ALL_NODES)
                    LOG.debug('Additional lookup for existing subscription '
                              'for EndpointUri %s ResourceAddress %s'
                              % (subscription_dto.EndpointUri,
                                 resource_address_star))
                    if self.subscription_repo.get_one(
                            EndpointUri=subscription_dto.EndpointUri,
                            ResourceAddress=resource_address_star) is not None:
                        LOG.debug('Found existing %s entry in subscription '
                                  'repo' % constants.WILDCARD_ALL_NODES)
                        raise client_exception.ServiceError(409)

                if nodename == constants.WILDCARD_CURRENT_NODE:
                    # There may be a subscription for the residing (current)
                    # node already in place
                    resource_address_synonym = \
                        subscription_helper.set_nodename_in_resource_address(
                            resource_address,
                            self.daemon_control.get_residing_nodename())
                    LOG.debug('In addition, looking for existing subscription '
                              'for EndpointUri %s ResourceAddress %s' % (
                                subscription_dto.EndpointUri,
                                resource_address_synonym))
                    entry = self.subscription_repo.get_one(
                        EndpointUri=subscription_dto.EndpointUri,
                        ResourceAddress=resource_address_synonym)

                if nodename == self.daemon_control.get_residing_nodename():
                    # There may be a subscription for '.' (current node)
                    # already in place
                    resource_address_synonym = \
                        subscription_helper.set_nodename_in_resource_address(
                            resource_address, constants.WILDCARD_CURRENT_NODE)
                    LOG.debug('In addition, looking for existing subscription '
                              'for EndpointUri %s ResourceAddress %s' % (
                                subscription_dto.EndpointUri,
                                resource_address_synonym))
                    entry = self.subscription_repo.get_one(
                        EndpointUri=subscription_dto.EndpointUri,
                        ResourceAddress=resource_address_synonym)

            if entry is not None:
                LOG.debug('Found existing v2 entry in subscription repo')
                raise client_exception.ServiceError(409)

            if nodename == constants.WILDCARD_ALL_NODES:
                broker_names = self.daemon_control.list_of_service_nodenames()
            else:
                broker_names = [nodename]

        elif hasattr(subscription_dto, 'ResourceType'):
            version = 1

            resource_qualifier_dto = \
                subscription_dto.ResourceQualifier.to_dict()
            LOG.debug('Looking for existing subscription for EndpointUri %s '
                      'ResourceQualifier %s' % (subscription_dto.EndpointUri,
                                                resource_qualifier_dto))
            entries = self.subscription_repo.get(
                EndpointUri=subscription_dto.EndpointUri)
            for entry in entries:
                resource_qualifier_json = entry.ResourceQualifierJson or '{}'
                resource_qualifier_repo = json.loads(resource_qualifier_json)
                if resource_qualifier_dto == resource_qualifier_repo:
                    LOG.debug('Found existing v1 entry in subscription repo')
                    raise client_exception.ServiceError(409)

            broker_names = [subscription_dto.ResourceQualifier.NodeName]

        nodes = {}  # node-ptpstatus pairs
        for broker in broker_names:
            default_node_name = NodeInfoHelper.default_node_name(broker)
            broker_pod_ip, supported_resource_types = self.__get_node_info(
                default_node_name)

            if not broker_pod_ip:
                LOG.warning("Node {0} is not available yet".format(
                    default_node_name))
                raise client_exception.NodeNotAvailable(broker)

            if ResourceType.TypePTP not in supported_resource_types:
                LOG.warning("Resource {0}@{1} is not available yet".format(
                    ResourceType.TypePTP, default_node_name))
                raise client_exception.ResourceNotAvailable(
                    broker, ResourceType.TypePTP)

            # get initial resource status
            ptpstatus = self._query(default_node_name, broker_pod_ip,
                                    resource_address, optional=None)
            LOG.info("Initial ptpstatus for {0}:{1}".format(default_node_name,
                                                            ptpstatus))

            # construct subscription entry
            if constants.PTP_V1_KEY in ptpstatus:
                timestamp = ptpstatus[constants.PTP_V1_KEY].get(
                    'EventTimestamp', None)
                ptpstatus = ptpstatus[constants.PTP_V1_KEY]
            else:
                for item in ptpstatus:
                    timestamp = ptpstatus[item].get('time', None)
                    # Change time from float to ascii format
                    ptpstatus[item]['time'] = datetime.fromtimestamp(
                        ptpstatus[item]['time']).strftime(
                            '%Y-%m-%dT%H:%M:%S%fZ')

            nodes[default_node_name] = ptpstatus

        subscription_orm = SubscriptionOrm(**subscription_dto.to_orm())
        subscription_orm.InitialDeliveryTimestamp = timestamp
        entry = self.subscription_repo.add(subscription_orm)

        # Delivery the initial notification of ptp status
        if version == 1:
            subscription_dto2 = SubscriptionInfoV1(entry)
        else:
            subscription_dto2 = SubscriptionInfoV2(entry)

        for node in nodes.items():
            try:
                subscription_helper.notify(subscription_dto2, node[1])
                LOG.info("Initial ptpstatus of {0} is delivered successfully"
                         "".format(node[0]))
            except Exception as ex:
                LOG.warning("Initial ptpstatus of {0} is not delivered:{1}"
                            "".format(node[0], str(ex)))
                raise client_exception.InvalidEndpoint(
                    subscription_dto.EndpointUri)

        try:
            # commit the subscription entry
            self.subscription_repo.commit()
            self.daemon_control.refresh()
        except Exception as ex:
            LOG.warning("subscription is not added successfully:"
                        "{0}".format(str(ex)))
            raise ex

        return subscription_dto2

    def remove_subscription(self, subscriptionid):
        try:
            # 1, delete entry
            self.subscription_repo.delete_one(SubscriptionId=subscriptionid)
            self.subscription_repo.commit()
            # 2, refresh daemon
            self.daemon_control.refresh()
        except Exception as ex:
            LOG.warning("subscription {0} is not deleted due to:"
                        "{1}/{2}".format(self.subscriptionid, type(ex),
                                         str(ex)))
            raise ex
