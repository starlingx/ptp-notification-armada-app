from pecan import make_app
from pecan.hooks import TransactionHook
from pecan import conf

from sidecar.repository.dbcontext_default import init_default_dbcontext, defaults
from sidecar.model import jsonify

def setup_app(config):

    # important to register jsonify for models
    jsonify.__init__()

    default_dbcontext = init_default_dbcontext(conf.sqlalchemy)
    app_conf = dict(config.app)

    return make_app(
        app_conf.pop('root'),
        logging=getattr(config, 'logging', {}),
        hooks=[
            TransactionHook(
                default_dbcontext.start,
                default_dbcontext.start_read_only,
                default_dbcontext.commit,
                default_dbcontext.rollback,
                default_dbcontext.clear
            )
        ],
        **app_conf
    )
