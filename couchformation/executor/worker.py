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


def get_class(module, instance, *args, **kwargs):
    m = __import__(module, fromlist=[""])
    i = getattr(m, instance)
    obj = i(*args, **kwargs)
    return obj


def run_method(obj, method, *args, **kwargs):
    f = getattr(obj, method)
    return f(*args, **kwargs)
