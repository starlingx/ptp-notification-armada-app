import logging

def get_logger(module_name):
    logger = logging.getLogger(module_name)
    return config_logger(logger)

def config_logger(logger):
    ''' 
    configure the logger: uncomment following lines for debugging
    '''
    # logger.setLevel(level=logging.DEBUG)
    return logger
