#
# Copyright (c) 2026 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
"""Unit tests for subscription resource-path ancestor matching.

Regression coverage for the subscription duplicate-detection fix: two
SyncE resources whose names share a raw string prefix
(/sync/synce-status/lock-state vs /sync/synce-status/lock-state-extended)
must be treated as independent, while a genuine parent path (/sync) must
still match its children.

The predicate is tested through subscription_helper (a dependency-light
module) rather than PtpService, whose import chain pulls in the
database/broker stack.
"""
from unittest import TestCase

from notificationclientsdk.common.helpers import subscription_helper

CLUSTER = 'testcluster'
NODE = 'controller-0'


def _path(resource):
    # parse_resource_address returns (cluster, node, resource_path, ...)
    return subscription_helper.parse_resource_address(
        '/%s/%s%s' % (CLUSTER, NODE, resource))[2]


LOCK_STATE = _path('/sync/synce-status/lock-state')
LOCK_STATE_EXT = _path('/sync/synce-status/lock-state-extended')
SYNC_AGGREGATE = _path('/sync')
PTP_STATUS = _path('/sync/ptp-status/lock-state')


class ResourcePathAncestorTests(TestCase):
    """Exercise resource_path_is_ancestor for the SyncE resource pair."""

    def _is_ancestor(self, a, b):
        return subscription_helper.resource_path_is_ancestor(a, b)

    def test_lock_state_and_extended_are_independent(self):
        # The raw-prefix bug reported these as duplicates in both directions.
        self.assertFalse(self._is_ancestor(LOCK_STATE, LOCK_STATE_EXT))
        self.assertFalse(self._is_ancestor(LOCK_STATE_EXT, LOCK_STATE))

    def test_identical_path_is_not_an_ancestor(self):
        # Equality is handled separately by the caller; a path is not its
        # own path-segment ancestor.
        self.assertFalse(self._is_ancestor(LOCK_STATE, LOCK_STATE))

    def test_sync_aggregate_is_ancestor_of_children(self):
        self.assertTrue(self._is_ancestor(SYNC_AGGREGATE, LOCK_STATE))
        self.assertTrue(self._is_ancestor(SYNC_AGGREGATE, LOCK_STATE_EXT))

    def test_child_is_not_ancestor_of_aggregate(self):
        self.assertFalse(self._is_ancestor(LOCK_STATE, SYNC_AGGREGATE))

    def test_siblings_in_different_subtrees_are_independent(self):
        # ptp-status/lock-state vs synce-status/lock-state must not match.
        self.assertFalse(self._is_ancestor(PTP_STATUS, LOCK_STATE))
        self.assertFalse(self._is_ancestor(LOCK_STATE, PTP_STATUS))
