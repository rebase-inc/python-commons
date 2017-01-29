import os
import math
import logging
import datetime
import itertools
import collections


OVERALL_KEY = '__overall__'
UNKNOWN_KEY = '__unknown__'
STDLIB_KEY = '__stdlib__'
PRIVATE_KEY = '__private__'

REPETITION_PENALTY = float(os.environ['REPETITION_PENALTY'])

class Knowledge(collections.defaultdict):
    VERSION = '1'

    def __init__(self, version = None, **kwargs):
        self.version = version or self.VERSION
        super().__init__(list, **kwargs)

    def add_reference(self, *args, date = None, count = 1) -> None:
        if args[0] == PRIVATE_KEY:
            return
        name = '.'.join(str(arg) for arg in args)
        self[name] += [ Reference(date) for _ in range(count) ]

    def penalize_repetition(self, knowledge) -> float:
        return math.log1p(knowledge / REPETITION_PENALTY) / math.log1p(1 / REPETITION_PENALTY)

    def normalize(self, depth = 2):
        '''
        This can't be done incrementally, because penalize_repetition(a + b) != penalize_repetition(a) + penalize_repetition(b).
        Technically, you could use the log identity of log(a + b) = log(a) + log(1 + b/a), but would make things a lot messier.
        Additionally, we probably want to save the non-normalized knowledge model. This normalized property could be instead
        done in a separate class, but that seems superfluous right now.
        '''
        normalized = collections.defaultdict(float)
        for name, references in self.items():
            name = name.split('.')[0:depth]
            name += (UNKNOWN_KEY, ) * (depth - len(name)) # pad to make sure args is of at least length "depth")
            name = '.'.join(name)
            score = round(self.penalize_repetition(sum(ref.activation for ref in references)), 4)
            normalized[name] += score 
            for module in itertools.accumulate(name.split('.')[0:depth - 1], lambda a, b: '{}.{}'.format(a, b)):
                normalized['{}.{}'.format(module, OVERALL_KEY)] += score 
        return normalized


class Reference(int):

    def __new__(cls, date):
        date = datetime.date.toordinal(date) if isinstance(date, datetime.date) else date
        return super(Reference, cls).__new__(cls, date)

    @property
    def activation(self):
        daysago = (datetime.date.today().toordinal() - self)
        return max(0.1, 1 / (1 + math.exp(daysago / 300 - 4)))

