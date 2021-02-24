#coding=utf-8
#
# Copyright (c) 2021 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from pecan import expose, redirect, rest, route, response
from webob.exc import status_map

from wsme import types as wtypes
from wsmeext.pecan import wsexpose

class HealthController(rest.RestController):

    @wsexpose(wtypes.text)
    def get(self):
        return {'health': True}


class RootController(object):
    pass


route(RootController, 'health', HealthController())
