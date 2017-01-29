import collections

import rq

class MeasuredJobProgress(object):

    def __init__(self, steps_key = 'steps', finished_key = 'finished'):
        self.steps = collections.Counter()
        self.finished = collections.Counter()
        self.steps_key = steps_key
        self.finished_key = finished_key
        self.job = rq.get_current_job()

    def add_step(self, name, count = 1):
        self.steps[name] += count
        self.report()

    def mark_finished(self, name, count = 1):
        self.finished[name] += count
        self.report()

    def report(self):
        self.job.meta[self.steps_key] = self.steps
        self.job.meta[self.finished_key] = self.finished
        self.job.save()

