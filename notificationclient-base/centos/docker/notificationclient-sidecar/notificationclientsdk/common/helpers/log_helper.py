#
# Copyright (c) 2021 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import os
import logging

LOGGING_LEVEL = os.environ.get("LOGGING_LEVEL", "INFO")

def get_logger(module_name):
    logger = logging.getLogger(module_name)
    return config_logger(logger)

def config_logger(logger):
    '''
    configure the logger: uncomment following lines for debugging
    '''
    logger.setLevel(LOGGING_LEVEL)
    return logger
