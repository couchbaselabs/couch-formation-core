##
##

import multiprocessing.queues


class TaskQueue(multiprocessing.queues.SimpleQueue):

    def __init__(self, *args, **kwargs):
        kwargs['ctx'] = multiprocessing.get_context('fork')
        super().__init__(*args, **kwargs)

    def send_task(self, module, instance, method, *args, **kwargs):
        m = __import__(module, fromlist=[""])
        i = getattr(m, instance)
        obj = i(*args, **kwargs)
        f = getattr(obj, method)
        self.put(f)

    def get_task(self):
        return self.get()
