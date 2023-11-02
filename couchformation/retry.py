##
##

import time
import asyncio
import logging
from typing import Callable
from functools import wraps

logger = logging.getLogger('couchformation.retry')
logger.addHandler(logging.NullHandler())


def retry_inline(func, *args, retry_count=10, factor=0.01, **kwargs):
    for retry_number in range(retry_count + 1):
        try:
            return func(*args, **kwargs)
        except Exception as err:
            if retry_number == retry_count:
                logger.debug(f"{func.__name__} retry limit exceeded: {err}")
                raise
            logger.debug(f"{func.__name__} will retry, number {retry_number + 1}")
            wait = factor
            wait *= (2 ** (retry_number + 1))
            time.sleep(wait)


def retry(retry_count=10,
          factor=0.01,
          allow_list=None,
          always_raise_list=None
          ) -> Callable:

    def retry_handler(func):
        if not asyncio.iscoroutinefunction(func):
            @wraps(func)
            def f_wrapper(*args, **kwargs):
                for retry_number in range(retry_count + 1):
                    try:
                        return func(*args, **kwargs)
                    except Exception as err:
                        if always_raise_list and isinstance(err, always_raise_list):
                            raise

                        if allow_list and not isinstance(err, allow_list):
                            raise

                        if retry_number == retry_count:
                            logger.debug(f"{func.__name__} retry limit exceeded")
                            raise

                        logger.debug(f"{func.__name__} will retry, number {retry_number + 1}")
                        wait = factor
                        wait *= (2 ** (retry_number + 1))
                        time.sleep(wait)

            return f_wrapper
        else:
            @wraps(func)
            async def f_wrapper(*args, **kwargs):
                for retry_number in range(retry_count + 1):
                    try:
                        return await func(*args, **kwargs)
                    except Exception as err:
                        if always_raise_list and isinstance(err, always_raise_list):
                            raise

                        if allow_list and not isinstance(err, allow_list):
                            raise

                        if retry_number == retry_count:
                            logger.debug(f"{func.__name__} retry limit exceeded")
                            raise

                        logger.debug(f"{func.__name__} will retry, number {retry_number + 1}")
                        wait = factor
                        wait *= (2 ** (retry_number + 1))
                        time.sleep(wait)

            return f_wrapper
    return retry_handler
