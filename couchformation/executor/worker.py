##
##

import logging

logger = logging.getLogger('couchformation.executor.worker')
logger.addHandler(logging.NullHandler())


def main(module, instance, method, *args, **kwargs):
    m = __import__(module, fromlist=[""])
    i = getattr(m, instance)
    obj = i(*args, **kwargs)
    f = getattr(obj, method)
    return f()
