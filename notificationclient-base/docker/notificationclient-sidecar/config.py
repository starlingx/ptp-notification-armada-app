#
# Copyright (c) 2021-2024 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import os
SIDECAR_API_PORT = os.environ.get("SIDECAR_API_PORT", "8080")
SIDECAR_API_HOST = os.environ.get("SIDECAR_API_HOST", "127.0.0.1")
DATASTORE_PATH = os.environ.get("DATASTORE_PATH", "/opt/datastore")
LOGGING_LEVEL = os.environ.get("LOGGING_LEVEL", "INFO")

# Server Specific Configurations
server = {
    'port': SIDECAR_API_PORT,
    'host': SIDECAR_API_HOST
}

# Pecan Application Configurations
# Ensure debug = False as per Pecan documentation
app = {
    'root': 'sidecar.controllers.root.RootController',
    'modules': ['sidecar'],
    'static_root': '%(confdir)s/public',
    'template_path': '%(confdir)s/sidecar/templates',
    'debug': False,
    'errors': {
        404: '/error/404',
        '__force_dict__': True
    }
}

logging = {
    'root': {'level': 'INFO', 'handlers': ['console']},
    'loggers': {
        'sidecar': {'level': LOGGING_LEVEL, 'handlers': ['console'], 'propagate': False},
        'pecan': {'level': LOGGING_LEVEL, 'handlers': ['console'], 'propagate': False},
        'py.warnings': {'handlers': ['console']},
        '__force_dict__': True
    },
    'handlers': {
        'console': {
            'level': LOGGING_LEVEL,
            'class': 'logging.StreamHandler',
            'formatter': 'color'
        }
    },
    'formatters': {
        'simple': {
            'format': ('%(asctime)s %(levelname)-5.5s [%(name)s]'
                       '[%(threadName)s] %(message)s')
        },
        'color': {
            '()': 'pecan.log.ColorFormatter',
            'format': ('%(asctime)s [%(padded_color_levelname)s] [%(name)s]'
                       '[%(threadName)s] %(message)s'),
            '__force_dict__': True
        }
    }
}

# Bindings and options to pass to SQLAlchemy's ``create_engine``
sqlalchemy = {
    'url': "sqlite:////{0}/sidecar.db".format(DATASTORE_PATH),
    'echo': False,
    'echo_pool': False,
    'pool_recycle': 3600,
    'encoding': 'utf-8'
}

# Custom Configurations must be in Python dictionary format::
#
# foo = {'bar':'baz'}
#
# All configurations are accessible at::
# pecan.conf
