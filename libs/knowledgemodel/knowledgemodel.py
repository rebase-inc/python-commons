import os
import abc
import math
import datetime
from collections import defaultdict, Counter

OVERALL_KEY = '__overall__'
UNKNOWN_KEY = '__unknown__'

TIME_REGULARIZATION = lambda daysago: max(0.1, (1 - math.exp(daysago / 200 - 2))) # TODO: Redesign and parameterize with environment variables
BREADTH_REGULARIZATION = lambda knowledge: math.log1p(knowledge / float(os.environ['BREADTH_DISCOUNT'])) * (1 / math.log1p( 1 / float(os.environ['BREADTH_DISCOUNT'])))

class KnowledgeLevel(defaultdict, metaclass = abc.ABCMeta):

    @abc.abstractmethod        
    def __init__(self, default_factory):
        super().__init__(default_factory)

    @property
    def reference_depth(self):
        if issubclass(self.default_factory, KnowledgeLevel):
            return 1 + self.default_factory().reference_depth
        else:
            return 1

    @property
    @abc.abstractmethod
    def simple_projection(self):
        pass

    def add_reference(self, *args, date = None, count = 1):
        args = args[0:self.reference_depth + 1]
        args += tuple(UNKNOWN_KEY for _ in range(self.reference_depth - len(args))) # pad to make sure args is of correct length
        self[args[0]].add_reference(*args[1:], date = date, count = count)

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__, dict.__repr__(self))

class KnowledgeLeaf(list, metaclass = abc.ABCMeta):

    @property
    @abc.abstractmethod
    def simple_projection(self):
        pass

    @abc.abstractmethod
    def add_reference(self, *args, date = None, count = 1):
        pass

    @abc.abstractmethod
    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__, list.__repr__(self))


class OverallKnowledge(KnowledgeLevel):

    def __init__(self):
        super().__init__(LanguageKnowledge)

    @property
    def simple_projection(self):
        return { name: language.simple_projection for name, language in self.items() }

class LanguageKnowledge(KnowledgeLevel):

    def __init__(self):
        super().__init__(ModuleKnowledge)

    @property
    def simple_projection(self):
        module_knowledge = { name: module.simple_projection for name, module in self.items() }
        module_knowledge[OVERALL_KEY] = sum(val for val in module_knowledge.values())
        return module_knowledge
    
class ModuleKnowledge(KnowledgeLevel):

    def __init__(self):
         super().__init__(SubmoduleKnowledge)

    @property
    def simple_projection(self):
        return BREADTH_REGULARIZATION(sum(submodule.simple_projection for submodule in self.values()))

class SubmoduleKnowledge(KnowledgeLeaf):

    def add_reference(self, date = None, count = 1):
        if not date:
            raise Exception('Date must be provided!')
        self.extend([ Reference(date) ] * count)

    @property
    def simple_projection(self):
        return BREADTH_REGULARIZATION(sum(ref.activation for ref in self))

class Reference(datetime.date):

    def __new__(cls, date, *args):
        date = super().fromordinal(date) if isinstance(date, int) else date
        return super(Reference, cls).__new__(cls, date.year, date.month, date.day) 

    @property
    def activation(self):
        daysago = (datetime.date.today() - self).days
        return TIME_REGULARIZATION(daysago)



if __name__ == '__main__':
    print('Breadth regularization of 1 is {}'.format(BREADTH_REGULARIZATION(1)))
    print('Breadth regularization of 2 is {}'.format(BREADTH_REGULARIZATION(2)))
    print()
    
    person_1 = OverallKnowledge()
    person_1.add_reference('python', 'socket', 'recv', date = datetime.date.today(), count = 1)
    person_1.add_reference('python', 'socket', 'recv', date = datetime.date.today(), count = 1)
    person_1.add_reference('python', 'socket', 'recv', date = datetime.date.today(), count = 1)
    person_1.add_reference('python', 'socket', 'recv', date = datetime.date.today(), count = 1)
    
    person_2 = OverallKnowledge()
    person_2.add_reference('python', 'socket', 'send', date = datetime.date.today(), count = 1)
    person_2.add_reference('python', 'socket', 'recv', date = datetime.date.today(), count = 1)
    person_2.add_reference('python', 'collections', 'defaultdict', date = datetime.date.today(), count = 1)
    person_2.add_reference('python', 'collections', 'Counter', date = datetime.date.today(), count = 1)
    
    person_3 = OverallKnowledge()
    person_3.add_reference('python', 'socket', 'recv', date = datetime.date.today() - datetime.timedelta(days=1800), count = 1)
    person_3.add_reference('python', 'socket', 'recv', date = datetime.date.today() - datetime.timedelta(days=1800), count = 1)
    person_3.add_reference('python', 'socket', 'recv', date = datetime.date.today() - datetime.timedelta(days=1800), count = 1)
    person_3.add_reference('python', 'socket', 'recv', date = datetime.date.today() - datetime.timedelta(days=1800), count = 1)

    print('Person 1\'s overall knowledge (narrow) is {}'.format(person_1.simple_projection['python'][OVERALL_KEY]))
    print('Person 2\'s overall knowledge (broad) is {}'.format(person_2.simple_projection['python'][OVERALL_KEY]))
    print('Person 3\'s overall knowledge (narrow and a long time ago) is {}'.format(person_3.simple_projection['python'][OVERALL_KEY]))
    print()
    print('Ratio of broad to narrow knowledge in this case is {}'.format(person_2.simple_projection['python'][OVERALL_KEY]/person_1.simple_projection['python'][OVERALL_KEY]))
    print()
