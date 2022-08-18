#
# Copyright (c) 2021-2022 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import logging
import sys
import os


def get_logger(module_name):
    logger = logging.getLogger(module_name)
    return config_logger(logger)


def config_logger(logger):
    logging.basicConfig(stream=sys.stdout)
    logger.setLevel(level=os.environ.get("LOGGING_LEVEL", "INFO"))
    return logger
