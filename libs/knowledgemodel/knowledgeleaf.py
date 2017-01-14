import os
import abc
import math
from typing import Union

KNOWLEDGE_WEIGHT_INVERSE = float(os.environ['KNOWLEDGE_WEIGHT_INVERSE'])

class KnowledgeLeaf(list, metaclass = abc.ABCMeta):

    @property
    @abc.abstractmethod
    def simple_projection(self):
        pass

    @abc.abstractmethod
    def add_reference(self, *args, date = None, count = 1):
        pass

    @abc.abstractmethod
    def breadth_regularization(self, knowledge: Union[float, int]) -> float:
        return math.log1p(knowledge / KNOWLEDGE_WEIGHT_INVERSE) / math.log1p(1 / KNOWLEDGE_WEIGHT_INVERSE)

    @abc.abstractmethod
    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__, list.__repr__(self))
