##
##

import logging
import concurrent.futures
import couchformation.executor.worker as worker
from couchformation.exception import NonFatalLogError

logger = logging.getLogger('couchformation.executor.dispatch')
logger.addHandler(logging.NullHandler())


class TaskError(NonFatalLogError):
    pass


class JobDispatch(object):

    def __init__(self):
        self.executor = concurrent.futures.ThreadPoolExecutor()
        self.tasks = set()

    def dispatch(self, *args, **kwargs):
        self.tasks.add(self.executor.submit(worker.main, *args, **kwargs))

    @staticmethod
    def foreground(*args, **kwargs):
        return worker.main(*args, **kwargs)

    def join(self):
        while self.tasks:
            done, self.tasks = concurrent.futures.wait(self.tasks, return_when=concurrent.futures.ALL_COMPLETED)
            for task in done:
                try:
                    res = task.result()
                    logger.debug(f"task result: {res}")
                    yield res
                except Exception as err:
                    raise TaskError(f"task exception: {err}")
