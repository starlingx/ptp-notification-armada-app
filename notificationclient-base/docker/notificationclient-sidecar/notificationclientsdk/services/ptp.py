#
# Copyright (c) 2021-2022 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import oslo_messaging
import logging
import json
import kombu

from notificationclientsdk.client.notificationservice import NotificationServiceClient
from notificationclientsdk.common.helpers import subscription_helper
from notificationclientsdk.common.helpers.nodeinfo_helper import NodeInfoHelper
from notificationclientsdk.model.dto.resourcetype import ResourceType
from notificationclientsdk.model.dto.subscription import SubscriptionInfoV1
from notificationclientsdk.model.dto.subscription import SubscriptionInfoV2
from notificationclientsdk.model.orm.subscription import Subscription as SubscriptionOrm
from notificationclientsdk.repository.node_repo import NodeRepo
from notificationclientsdk.repository.subscription_repo import SubscriptionRepo
from notificationclientsdk.services.daemon import DaemonControl


from notificationclientsdk.exception import client_exception

LOG = logging.getLogger(__name__)

from notificationclientsdk.common.helpers import log_helper
log_helper.config_logger(LOG)

class PtpService(object):

    def __init__(self, daemon_control):
        self.daemon_control = daemon_control
        self.locationservice_client = daemon_control.locationservice_client
        self.subscription_repo = SubscriptionRepo(autocommit=False)

    def __del__(self):
        del self.subscription_repo
        self.locationservice_client = None
        return

    def __query_locationinfo(self, broker_name, timeout=5, retry=2):
        try:
            location_info = self.locationservice_client.query_location(broker_name, timeout, retry)
            LOG.debug("Pulled location info@{0}:{1}".format(broker_name, location_info))
            return location_info
        except Exception as ex:
            LOG.warning("Failed to query location of node:{0} due to: {1}".format(
                broker_name, str(ex)))
            raise client_exception.NodeNotAvailable(broker_name)

    def __get_node_info(self, default_node_name, timeout=5, retry=2):
        try:
            nodeinfo_repo = NodeRepo(autocommit=False)
            nodeinfo = nodeinfo_repo.get_one(Status=1, NodeName=default_node_name)
            broker_pod_ip = None
            supported_resource_types = []

            if nodeinfo:
                broker_pod_ip = nodeinfo.PodIP
                supported_resource_types = json.loads(nodeinfo.ResourceTypes or '[]')

            if not broker_pod_ip:
                # try to query the broker ip
                location_info = self.__query_locationinfo(default_node_name, timeout, retry)
                broker_pod_ip = location_info.get("PodIP", None)
                supported_resource_types = location_info.get("ResourceTypes", [])

            return broker_pod_ip, supported_resource_types
        finally:
            del nodeinfo_repo

    def query(self, broker_name, resource_address=None):
        default_node_name = NodeInfoHelper.default_node_name(broker_name)
        broker_pod_ip, supported_resource_types = self.__get_node_info(default_node_name)

        if not broker_pod_ip:
            LOG.warning("Node {0} is not available yet".format(default_node_name))
            raise client_exception.NodeNotAvailable(broker_name)

        if not ResourceType.TypePTP in supported_resource_types:
            LOG.warning("Resource {0}@{1} is not available yet".format(
                ResourceType.TypePTP, default_node_name))
            raise client_exception.ResourceNotAvailable(broker_name, ResourceType.TypePTP)

        return self._query(default_node_name, broker_pod_ip, resource_address)

    def _query(self, broker_name, broker_pod_ip, resource_address=None):
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
                ResourceType.TypePTP, timeout=5, retry=10, resource_address=resource_address)
            return resource_status
        except oslo_messaging.exceptions.MessagingTimeout as ex:
            LOG.warning("ptp status is not available @node {0} due to {1}".format(
                broker_name, str(ex)))
            raise client_exception.ResourceNotAvailable(broker_name, ResourceType.TypePTP)
        except kombu.exceptions.OperationalError as ex:
            LOG.warning("Node {0} is unreachable yet".format(broker_name))
            raise client_exception.NodeNotAvailable(broker_name)
        finally:
            if notificationservice_client:
                notificationservice_client.cleanup()
                del notificationservice_client

    def add_subscription(self, subscription_dto):
        subscription_orm = SubscriptionOrm(**subscription_dto.to_orm())
        if hasattr(subscription_dto, 'ResourceAddress'):
            _,nodename,_ = subscription_helper.parse_resource_address(subscription_dto.ResourceAddress)
            broker_name = nodename
        elif hasattr(subscription_dto, 'ResourceType'):
            broker_name = subscription_dto.ResourceQualifier.NodeName
        default_node_name = NodeInfoHelper.default_node_name(broker_name)

        broker_pod_ip, supported_resource_types = self.__get_node_info(default_node_name)

        if not broker_pod_ip:
            LOG.warning("Node {0} is not available yet".format(default_node_name))
            raise client_exception.NodeNotAvailable(broker_name)

        if not ResourceType.TypePTP in supported_resource_types:
            LOG.warning("Resource {0}@{1} is not available yet".format(
                ResourceType.TypePTP, default_node_name))
            raise client_exception.ResourceNotAvailable(broker_name, ResourceType.TypePTP)

        # get initial resource status
        if default_node_name:

            ptpstatus = None
            ptpstatus = self._query(default_node_name, broker_pod_ip)
            LOG.info("initial ptpstatus:{0}".format(ptpstatus))

            # construct subscription entry
            subscription_orm.InitialDeliveryTimestamp = ptpstatus.get('EventTimestamp', None)
            entry = self.subscription_repo.add(subscription_orm)

            # Delivery the initial notification of ptp status
            if hasattr(subscription_dto, 'ResourceType'):
                subscription_dto2 = SubscriptionInfoV1(entry)
            else:
                subscription_dto2 = SubscriptionInfoV2(entry)

            try:
                subscription_helper.notify(subscription_dto2, ptpstatus)
                LOG.info("initial ptpstatus is delivered successfully")
            except Exception as ex:
                LOG.warning("initial ptpstatus is not delivered:{0}".format(str(ex)))
                raise client_exception.InvalidEndpoint(subscription_dto.EndpointUri)

            try:
                # commit the subscription entry
                self.subscription_repo.commit()
                self.daemon_control.refresh()
            except Exception as ex:
                LOG.warning("subscription is not added successfully:{0}".format(str(ex)))
                raise ex
        return subscription_dto2

    def remove_subscription(self, subscriptionid):
        try:
            # 1, delete entry
            self.subscription_repo.delete_one(SubscriptionId = subscriptionid)
            self.subscription_repo.commit()
            # 2, refresh daemon
            self.daemon_control.refresh()
        except Exception as ex:
            LOG.warning("subscription {0} is not deleted due to:{1}/{2}".format(
                self.subscriptionid, type(ex), str(ex)))
            raise ex
