import logging
#
# Copyright (c) 2021 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

def get_logger(module_name):
    logger = logging.getLogger(module_name)
    return config_logger(logger)

def config_logger(logger):
    '''
    configure the logger: uncomment following lines for debugging
    '''
    # logger.setLevel(level=logging.DEBUG)
    return logger