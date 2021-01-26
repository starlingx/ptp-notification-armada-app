import os
SIDECAR_API_PORT = os.environ.get("SIDECAR_API_PORT", "8080")
SIDECAR_API_HOST = os.environ.get("SIDECAR_API_HOST", "127.0.0.1")
# Server Specific Configurations
server = {
    'port': SIDECAR_API_PORT,
    'host': SIDECAR_API_HOST
}

# Pecan Application Configurations
app = {
    'root': 'sidecar.controllers.root.RootController',
    'modules': ['sidecar'],
    'static_root': '%(confdir)s/public',
    'template_path': '%(confdir)s/sidecar/templates',
    'debug': True,
    'errors': {
        404: '/error/404',
        '__force_dict__': True
    }
}

logging = {
    'root': {'level': 'INFO', 'handlers': ['console']},
    'loggers': {
        'sidecar': {'level': 'DEBUG', 'handlers': ['console'], 'propagate': False},
        'pecan': {'level': 'DEBUG', 'handlers': ['console'], 'propagate': False},
        'py.warnings': {'handlers': ['console']},
        '__force_dict__': True
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
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
    'url'           : 'sqlite:///sidecar.db',
    'echo'          : False,
    'echo_pool'     : False,
    'pool_recycle'  : 3600,
    'encoding'      : 'utf-8'
}

# Custom Configurations must be in Python dictionary format::
#
# foo = {'bar':'baz'}
#
# All configurations are accessible at::
# pecan.conf
