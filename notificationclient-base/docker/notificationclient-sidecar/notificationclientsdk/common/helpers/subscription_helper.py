#
# Copyright (c) 2021-2024 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import json
import logging
import re
from datetime import datetime

import requests
from notificationclientsdk.common.helpers import constants, log_helper
from notificationclientsdk.exception import client_exception

LOG = logging.getLogger(__name__)
log_helper.config_logger(LOG)


def notify(subscriptioninfo, notification, timeout=2, retry=3):
    result = False
    while True:
        retry = retry - 1
        try:
            headers = {'Content-Type': 'application/json'}
            url = subscriptioninfo.EndpointUri
            if 'ResourceType' in notification:
                # version 1
                data = format_notification_data(subscriptioninfo, notification)
                data = json.dumps(data)
                response = requests.post(url, data=data, headers=headers,
                                        timeout=timeout)
                response.raise_for_status()
            else:
                if isinstance(notification, list):
                    # List-type notification response format
                    LOG.debug("Formatting subscription response: list")
                    # Post notification for each list item
                    for item in notification:
                        data = json.dumps(item)
                        LOG.info("Notification to post %s", (data))
                        response = requests.post(url, data=data, headers=headers,
                                                timeout=timeout)
                        response.raise_for_status()
                else:
                    # Dict type notification response format
                    LOG.debug("Formatting subscription response: dict")
                    if notification.get('id', None):
                        # Not a nested dict, post the data
                        data = json.dumps(notification)
                        LOG.info("Notification to post %s", (data))
                        response = requests.post(url, data=data, headers=headers,
                                                timeout=timeout)
                        response.raise_for_status()
                    else:
                        for item in notification:
                            # Nested dict with instance tags, post each item
                            data = format_notification_data(subscriptioninfo, {item: notification[item]})
                            data = json.dumps(data)
                            LOG.info("Notification to post %s", (data))
                            response = requests.post(url, data=data, headers=headers,
                                                    timeout=timeout)
                            response.raise_for_status()

            if notification == {}:
                if hasattr(subscriptioninfo, 'ResourceType'):
                    resource = "{'ResourceType':'" + \
                        subscriptioninfo.ResourceType + "'}"
                elif hasattr(subscriptioninfo, 'ResourceAddress'):
                    _, _, resource, _, _ = parse_resource_address(
                        subscriptioninfo.ResourceAddress)
                raise client_exception.InvalidResource(resource)
            result = True
            return response
        except client_exception.InvalidResource as ex:
            raise ex
        except requests.exceptions.ConnectionError as errc:
            if retry > 0:
                LOG.warning("Retry notifying due to: {0}".format(str(errc)))
                continue
            raise errc
        except requests.exceptions.Timeout as errt:
            if retry > 0:
                LOG.warning("Retry notifying due to: {0}".format(str(errt)))
                continue
            raise errt
        except requests.exceptions.RequestException as ex:
            LOG.warning("Failed to notify due to: {0}".format(str(ex)))
            LOG.warning(" %s", (notification))
            raise ex
        except requests.exceptions.HTTPError as ex:
            LOG.warning("Failed to notify due to: {0}".format(str(ex)))
            raise ex
        except Exception as ex:
            LOG.warning("Failed to notify due to: {0}".format(str(ex)))
            raise ex

    return result

def format_notification_data(subscriptioninfo, notification):
    if isinstance(notification, list):
        return notification

    # Formatting for legacy notification
    if hasattr(subscriptioninfo, 'ResourceType'):
        LOG.debug("format_notification_data: Found v1 subscription, "
                  "no formatting required.")
        return notification
    elif hasattr(subscriptioninfo, 'ResourceAddress'):
        _, _, resource_path, _, _ = parse_resource_address(
            subscriptioninfo.ResourceAddress)
        if resource_path not in constants.RESOURCE_ADDRESS_MAPPINGS.keys():
            raise client_exception.InvalidResource(resource_path)
        resource_mapped_value = constants.RESOURCE_ADDRESS_MAPPINGS[
            resource_path]
        formatted_notification = {resource_mapped_value: []}
        for instance in notification:
            # Add the instance identifier to ResourceAddress for PTP lock-state
            # and PTP clockClass
            if notification[instance]['source'] in [
                    constants.SOURCE_SYNC_PTP_CLOCK_CLASS,
                    constants.SOURCE_SYNC_PTP_LOCK_STATE]:
                temp_values = notification[instance].get('data', {}).get(
                    'values', [])
                resource_address = temp_values[0].get('ResourceAddress', None)
                if instance not in resource_address:
                    add_instance_name = resource_address.split('/', 3)
                    add_instance_name.insert(3, instance)
                    resource_address = '/'.join(add_instance_name)
                    notification[instance]['data']['values'][0][
                        'ResourceAddress'] = resource_address
            formatted_notification[resource_mapped_value].append(
                notification[instance])
        for instance in formatted_notification[resource_mapped_value]:
            this_delivery_time = instance['time']
            if type(this_delivery_time) != str:
                format_time = datetime.fromtimestamp(
                    float(this_delivery_time)).strftime('%Y-%m-%dT%H:%M:%S%fZ')
                instance['time'] = format_time
    else:
        LOG.warning("format_notification_data: No valid source "
                        "address found in notification")
    LOG.debug("format_notification_data: Added parent key for client "
              "consumption: %s" % formatted_notification)
    return formatted_notification


def parse_resource_address(resource_address):
    # The format of resource address is:
    # /{clusterName}/{siteName}(/optional/hierarchy/..)/{nodeName}/{resource}
    clusterName = resource_address.split('/')[1]
    nodeName = resource_address.split('/')[2]
    resource_path = '/' + re.split('[/]', resource_address, 3)[3]
    resource_list = re.findall(r'[^/]+', resource_path)
    if len(resource_list) == 4:
        remove_optional = '/' + resource_list[0]
        resource_path = resource_path.replace(remove_optional, '')
        resource_address = resource_address.replace(remove_optional, '')
        optional = resource_list[0]
        LOG.debug("Optional hierarchy found when parsing resource address: %s"
                  % optional)
    else:
        optional = None

    # resource_address is the full address without any optional hierarchy
    # resource_path is the specific identifier for the resource
    return clusterName, nodeName, resource_path, optional, resource_address


def set_nodename_in_resource_address(resource_address, nodename):
    # The format of resource address is:
    # /{clusterName}/{siteName}(/optional/hierarchy/..)/{nodeName}/{resource}
    cluster, _, path, optional, _ = parse_resource_address(
        resource_address)
    resource_address = '/' + cluster + '/' + nodename
    if optional:
        resource_address += '/' + optional
    resource_address += path
    return resource_address
