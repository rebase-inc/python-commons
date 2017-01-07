import os
import json
import math
import time
import boto3
import logging
import datetime

from typing import Union

from .knowledgelevel import KnowledgeLevel
from .knowledgeleaf import KnowledgeLeaf

OVERALL_KEY = '__overall__'

LOGGER = logging.getLogger()
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('botocore').setLevel(logging.WARNING)

class KnowledgeModel(KnowledgeLevel):

    def __init__(self):
        super().__init__(LanguageKnowledge)

    @property
    def simple_projection(self):
        return { name: language.simple_projection for name, language in self.items() }

    def write_to_s3(self, username, bucket, s3config):
        written_objects = {}
        s3bucket = boto3.resource('s3', **s3config).Bucket(bucket)
        knowledge_object = s3bucket.Object('users/{}'.format(username))
        etag = knowledge_object.put(Body = json.dumps(self.simple_projection))['ETag']
        written_objects[etag] = knowledge_object

        for lang_name, lang_knowledge in self.simple_projection.items():
            for mod_name, mod_knowledge in lang_knowledge.items():
                prefix = 'leaderboard/{}/{}/{}'.format(lang_name, mod_name, username)
                for obj in s3bucket.objects.filter(Prefix = prefix):
                    obj.delete()
                key = prefix + ':{:.2f}'.format(mod_knowledge)
                obj = s3bucket.Object(key = key)
                etag = obj.put(Body = bytes('', 'utf-8'))['ETag']
                written_objects[etag] = obj

        start = time.time()
        LOGGER.debug('Waiting for s3 writes to finish...')
        for etag, obj in written_objects.items():
            obj.wait_until_exists(IfMatch = etag)
        LOGGER.debug('Writing all objects to s3 took {} seconds'.format(time.time() - start))


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
        return super().breadth_regularization(sum(submodule.simple_projection for submodule in self.values()))

class SubmoduleKnowledge(KnowledgeLeaf):

    def add_reference(self, date = None, count = 1):
        self.extend([ Reference(date) ] * count)

    @property
    def simple_projection(self):
        return super().breadth_regularization(sum(ref.activation for ref in self))

class Reference(datetime.date):

    def __new__(cls, date, *args):
        date = super().fromordinal(date) if isinstance(date, int) else date
        return super(Reference, cls).__new__(cls, date.year, date.month, date.day)

    @property
    def activation(self):
        daysago = (datetime.date.today() - self).days
        return max(0.1, 1 / (1 + math.exp(daysago / 300 - 4)))

if __name__ == '__main__':
    import numpy
    from matplotlib import pyplot
    today = datetime.date.today().toordinal()
    def _make_fake_knowledge_by_date(ordinaldate):
        k = KnowledgeModel()
        k.add_reference('a','b','c', date = datetime.date.fromordinal(today + ordinaldate), count = 1)
        return k.simple_projection['a'][OVERALL_KEY]
    make_fake_knowledge_by_date = numpy.vectorize(_make_fake_knowledge_by_date)
    dates = numpy.arange(-3600, 0, 10)
    pyplot.plot(dates, make_fake_knowledge_by_date(dates))
    pyplot.title('Knowledge by number of days ago')
    pyplot.show()

    import uuid
    def _make_fake_knowledge_by_breadth(breadth_as_percentage, total_count = 2000):
        k = KnowledgeModel()
        unique_modules = max(int(breadth_as_percentage * total_count), 1)
        extra_per = int((total_count - unique_modules) / unique_modules)
        for _ in range(unique_modules):
            k.add_reference('fakelang', uuid.uuid4(), date = datetime.date.today(), count = 1 + extra_per)
        return k.simple_projection['fakelang'][OVERALL_KEY]
    make_fake_knowledge_by_breadth = numpy.vectorize(_make_fake_knowledge_by_breadth)
    percentages = numpy.arange(0, 0.6, 0.02)
    pyplot.plot(percentages, make_fake_knowledge_by_breadth(percentages))
    pyplot.title('Knowledge by breadth as percentage')
    pyplot.show()

    def _make_fake_knowledge_by_count(count):
        k = KnowledgeModel()
        k.add_reference('a','b', date = datetime.date.today(), count = count)
        return k.simple_projection['a'][OVERALL_KEY]
    make_fake_knowledge_by_count = numpy.vectorize(_make_fake_knowledge_by_count)
    counts = numpy.arange(0, 500, 10)
    pyplot.plot(counts, make_fake_knowledge_by_count(counts))
    pyplot.title('Knowledge by reference count')
    pyplot.show()



    person_1 = KnowledgeModel()
    person_1.add_reference('python', 'socket', 'recv', date = datetime.date.today(), count = 1)
    person_1.add_reference('python', 'socket', 'recv', date = datetime.date.today(), count = 1)
    person_1.add_reference('python', 'socket', 'recv', date = datetime.date.today(), count = 1)
    person_1.add_reference('python', 'socket', 'recv', date = datetime.date.today(), count = 1)

    person_2 = KnowledgeModel()
    person_2.add_reference('python', 'socket', 'send', date = datetime.date.today(), count = 1)
    person_2.add_reference('python', 'socket', 'recv', date = datetime.date.today(), count = 1)
    person_2.add_reference('python', 'collections', 'defaultdict', date = datetime.date.today(), count = 1)
    person_2.add_reference('python', 'collections', 'Counter', date = datetime.date.today(), count = 1)

    person_3 = KnowledgeModel()
    person_3.add_reference('python', 'socket', 'recv', date = datetime.date.today() - datetime.timedelta(days=1800), count = 1)
    person_3.add_reference('python', 'socket', 'recv', date = datetime.date.today() - datetime.timedelta(days=1800), count = 1)
    person_3.add_reference('python', 'socket', 'recv', date = datetime.date.today() - datetime.timedelta(days=1800), count = 1)
    person_3.add_reference('python', 'socket', 'recv', date = datetime.date.today() - datetime.timedelta(days=1800), count = 1)

    person_4 = KnowledgeModel()
    person_4.add_reference('python', 'socket', 'recv', date = datetime.date.today() - datetime.timedelta(days=365), count = 1)
    person_4.add_reference('python', 'socket', 'recv', date = datetime.date.today() - datetime.timedelta(days=365), count = 1)
    person_4.add_reference('python', 'socket', 'recv', date = datetime.date.today() - datetime.timedelta(days=365), count = 1)
    person_4.add_reference('python', 'socket', 'recv', date = datetime.date.today() - datetime.timedelta(days=365), count = 1)

    person_5 = KnowledgeModel()
    person_5.add_reference('python', 'socket', 'recv', date = datetime.date.today() - datetime.timedelta(days=2*365), count = 1)
    person_5.add_reference('python', 'socket', 'recv', date = datetime.date.today() - datetime.timedelta(days=2*365), count = 1)
    person_5.add_reference('python', 'socket', 'recv', date = datetime.date.today() - datetime.timedelta(days=2*365), count = 1)
    person_5.add_reference('python', 'socket', 'recv', date = datetime.date.today() - datetime.timedelta(days=2*365), count = 1)

    print('Person 1\'s knowledge (narrow) looks like {}'.format(person_1.simple_projection))
    print()
    print('Person 1\'s overall knowledge (narrow) is {}'.format(person_1.simple_projection['python'][OVERALL_KEY]))
    print('Person 2\'s overall knowledge (broad) is {}'.format(person_2.simple_projection['python'][OVERALL_KEY]))
    print('Person 3\'s overall knowledge (narrow and a long time ago) is {}'.format(person_3.simple_projection['python'][OVERALL_KEY]))
    print('Person 4\'s overall knowledge (narrow and year ago) is {}'.format(person_4.simple_projection['python'][OVERALL_KEY]))
    print('Person 4\'s overall knowledge (narrow and two years ago) is {}'.format(person_5.simple_projection['python'][OVERALL_KEY]))
    print()
    print('Ratio of broad to narrow knowledge in this case is {}'.format(person_2.simple_projection['python'][OVERALL_KEY]/person_1.simple_projection['python'][OVERALL_KEY]))
    print()

    # testing incorrect length references
    person_3.add_reference('python', date = datetime.date.today() - datetime.timedelta(days=1800), count = 1)
    person_3.add_reference('python', 'socket', 'socket', 'recv', date = datetime.date.today() - datetime.timedelta(days=1800), count = 1)

