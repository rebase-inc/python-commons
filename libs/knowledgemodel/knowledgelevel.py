import os
import abc
import math
import logging
import datetime
from typing import Union
from collections import defaultdict

KNOWLEDGE_WEIGHT_INVERSE = float(os.environ['KNOWLEDGE_WEIGHT_INVERSE'])
UNKNOWN_KEY = '__unknown__'
LOGGER = logging.getLogger()

# TODO: Fix this class so it properly throws when not subclassed (proper ABC behavior)
class KnowledgeLevel(defaultdict, metaclass = abc.ABCMeta):

    @abc.abstractmethod
    def __init__(self, default_factory):
        super().__init__(default_factory)

    @property
    def reference_depth(self) -> int:
        if issubclass(self.default_factory, KnowledgeLevel):
            return 1 + self.default_factory().reference_depth
        else:
            return 1

    @property
    @abc.abstractmethod
    def simple_projection(self):
        pass

    @abc.abstractmethod
    def breadth_regularization(self, knowledge: Union[float, int]) -> float:
        return math.log1p(knowledge / KNOWLEDGE_WEIGHT_INVERSE) / math.log1p(1 / KNOWLEDGE_WEIGHT_INVERSE)

    def add_reference(self, *args, date: datetime.date = None, count: int = 1) -> None:
        args = args[0:self.reference_depth - 1]
        args += tuple(UNKNOWN_KEY for _ in range(self.reference_depth - len(args))) # pad to make sure args is of correct length
        self[args[0]].add_reference(*args[1:], date = date, count = count)

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__, dict.__repr__(self))
