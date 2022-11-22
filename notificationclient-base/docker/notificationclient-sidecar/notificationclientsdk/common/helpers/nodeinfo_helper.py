#
# Copyright (c) 2021 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import logging
from notificationclientsdk.repository.node_repo import NodeRepo
from notificationclientsdk.common.helpers import constants
from notificationclientsdk.common.helpers import log_helper

LOG = logging.getLogger(__name__)
log_helper.config_logger(LOG)


class NodeInfoHelper(object):
    residing_node_name = None

    @staticmethod
    def set_residing_node(residing_node_name):
        NodeInfoHelper.residing_node_name = residing_node_name

    @staticmethod
    def get_residing_node():
        residing_node_name = NodeInfoHelper.residing_node_name
        return residing_node_name

    @staticmethod
    def expand_node_name(node_name_pattern):
        if node_name_pattern == constants.WILDCARD_CURRENT_NODE:
            return NodeInfoHelper.residing_node_name
        else:
            return node_name_pattern

    @staticmethod
    def default_node_name(node_name_pattern):
        if node_name_pattern == constants.WILDCARD_CURRENT_NODE:
            return NodeInfoHelper.residing_node_name
        else:
            return node_name_pattern

    @staticmethod
    def match_node_name(node_name_pattern, target_node_name):
        if node_name_pattern == constants.WILDCARD_ALL_NODES:
            return True
        elif node_name_pattern == constants.WILDCARD_CURRENT_NODE:
            return NodeInfoHelper.residing_node_name == target_node_name
        else:
            return node_name_pattern == target_node_name

    @staticmethod
    def enumerate_nodes(node_name_pattern):
        '''
        enumerate nodes from node repo by pattern
        '''
        nodeinfos = []
        if not node_name_pattern:
            raise ValueError("node name pattern is invalid")

        nodeinfo_repo = None
        try:
            nodeinfo_repo = NodeRepo(autocommit=True)
            filter = {}
            if node_name_pattern == constants.WILDCARD_ALL_NODES:
                pass
            elif not node_name_pattern or \
                    node_name_pattern == constants.WILDCARD_CURRENT_NODE:
                filter = {'NodeName': NodeInfoHelper.residing_node_name}
            else:
                filter = {'NodeName': node_name_pattern}

            nodeinfos = [x.NodeName
                         for x in nodeinfo_repo.get(Status=1, **filter)]

        except Exception as ex:
            LOG.warning("Failed to enumerate nodes:{0}".format(str(ex)))
            nodeinfos = None
        finally:
            if nodeinfo_repo:
                del nodeinfo_repo

        return nodeinfos
