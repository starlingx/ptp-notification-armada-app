#
# Copyright (c) 2021 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import kombu.utils.functional

class OsloMessagingPatcher(object):
    retry_over_time_orig = None
    @staticmethod
    def retry_over_time_patch(
        fun, catch, args=None, kwargs=None, errback=None,
        max_retries=None, interval_start=2, interval_step=2,
        interval_max=30, callback=None, timeout=None):
        """
        patch to retry_over_time with default max_retries=5
        """
        if not max_retries:
            max_retries = 2
        return OsloMessagingPatcher.retry_over_time_orig(
            fun, catch, args, kwargs, errback,
            max_retries, interval_start, interval_step,
            interval_max, callback, timeout)

    @staticmethod
    def patch():
        if not OsloMessagingPatcher.retry_over_time_orig:
            OsloMessagingPatcher.retry_over_time_orig = kombu.utils.functional.retry_over_time
            kombu.utils.functional.retry_over_time = OsloMessagingPatcher.retry_over_time_patch
        return
