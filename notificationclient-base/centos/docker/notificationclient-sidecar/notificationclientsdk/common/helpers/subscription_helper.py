#coding=utf-8

import os
import json

import requests
import logging

from notificationclientsdk.common.helpers.nodeinfo_helper import NodeInfoHelper

LOG = logging.getLogger(__name__)

from notificationclientsdk.common.helpers import log_helper
log_helper.config_logger(LOG)

def notify(subscriptioninfo, notification, timeout=2, retry=3):
    result = False
    while True:
        retry = retry - 1
        try:
            headers = {'Content-Type': 'application/json'}
            data = json.dumps(notification)
            url = subscriptioninfo.EndpointUri
            response = requests.post(url, data=data, headers=headers, timeout=timeout)
            response.raise_for_status()
            result = True
            return response
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
            raise ex
        except requests.exceptions.HTTPError as ex:
            LOG.warning("Failed to notify due to: {0}".format(str(ex)))
            raise ex
        except Exception as ex:
            LOG.warning("Failed to notify due to: {0}".format(str(ex)))
            raise ex

    return result

