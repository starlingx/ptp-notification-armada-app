import oslo_messaging
import logging

from notificationclientsdk.repository.node_repo import NodeRepo
from notificationclientsdk.repository.subscription_repo import SubscriptionRepo
from notificationclientsdk.model.dto.resourcetype import ResourceType
from notificationclientsdk.model.dto.subscription import SubscriptionInfo
from notificationclientsdk.common.helpers.nodeinfo_helper import NodeInfoHelper
from notificationclientsdk.model.orm.subscription import Subscription as SubscriptionOrm
from notificationclientsdk.client.notificationservice import NotificationServiceClient
from notificationclientsdk.services.daemon import DaemonControl
from notificationclientsdk.common.helpers import subscription_helper

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
        return

    def query(self, broker_node_name):
        broker_host = "notificationservice-{0}".format(broker_node_name)
        broker_transport_endpoint = "rabbit://{0}:{1}@{2}:{3}".format(
            self.daemon_control.daemon_context['NOTIFICATION_BROKER_USER'],
            self.daemon_control.daemon_context['NOTIFICATION_BROKER_PASS'],
            broker_host,
            self.daemon_control.daemon_context['NOTIFICATION_BROKER_PORT'])
        notificationservice_client = NotificationServiceClient(
            broker_node_name, broker_transport_endpoint)
        resource_status = notificationservice_client.query_resource_status(
            ResourceType.TypePTP, timeout=5, retry=10)
        del notificationservice_client
        return resource_status

    def add_subscription(self, subscription_dto):
        subscription_orm = SubscriptionOrm(**subscription_dto.to_orm())
        broker_node_name = subscription_dto.ResourceQualifier.NodeName
        default_node_name = NodeInfoHelper.default_node_name(broker_node_name)
        nodeinfos = NodeInfoHelper.enumerate_nodes(broker_node_name)
        # 1, check node availability from DB
        if not nodeinfos or not default_node_name in nodeinfos:
            # update nodeinfo
            try:
                nodeinfo = self.locationservice_client.update_location(
                    default_node_name, timeout=5, retry=2)
            except oslo_messaging.exceptions.MessagingTimeout as ex:
                LOG.warning("node {0} cannot be reached due to {1}".format(
                    default_node_name, str(ex)))
                raise ex

        # 2, add to DB
        entry = self.subscription_repo.add(subscription_orm)
        # must commit the transaction to make it visible to daemon worker
        self.subscription_repo.commit()

        # 3, refresh daemon
        self.daemon_control.refresh()

        # 4, get initial resource status
        if default_node_name:
            ptpstatus = None
            try:
                ptpstatus = self.query(default_node_name)
                LOG.info("initial ptpstatus:{0}".format(ptpstatus))
            except oslo_messaging.exceptions.MessagingTimeout as ex:
                LOG.warning("ptp status is not available @node {0} due to {1}".format(
                    default_node_name, str(ex)))
                # remove the entry
                self.subscription_repo.delete_one(SubscriptionId = entry.SubscriptionId)
                self.subscription_repo.commit()
                self.daemon_control.refresh()
                raise ex

            # 5, initial delivery of ptp status
            subscription_dto2 = SubscriptionInfo(entry)
            try:
                subscription_helper.notify(subscription_dto2, ptpstatus)
                LOG.info("initial ptpstatus is delivered successfully")
            except Exception as ex:
                LOG.warning("initial ptpstatus is not delivered:{0}".format(type(ex), str(ex)))
                # remove the entry
                self.subscription_repo.delete_one(SubscriptionId = entry.SubscriptionId)
                self.subscription_repo.commit()
                self.daemon_control.refresh()
                subscription_dto2 = None
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
