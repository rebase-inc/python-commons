import re
import os
import json
import math
import time
import bisect
import pickle
import logging
import datetime
import functools

from typing import Union

import boto3
import botocore
import psycopg2

OVERALL_KEY = '__overall__'
STDLIB_KEY = '__stdlib__'
PRIVATE_KEY = '__private__'

LOGGER = logging.getLogger()
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('botocore').setLevel(logging.WARNING)

class KnowledgeModel(defaultdict):
    VERSION = '1'

    def __init__(self, username = None, bucket = None, s3config = None):
        super().__init__(list)
        self.username = username
        self.bucket_name = bucket
        self.s3config = s3config

    def add_reference(self, *args, date: datetime.date = None, count: int = 1) -> None:
        name = '.'.join(str(arg) for arg in args)
        self[name] += [ Reference(date) for _ in range(count)]

    def normalize(self, depth = 3):
        normalized = defaultdict(int)
        for name, references in self.items():
            normalized[name.split('.')[0:depth - 1].join('.')] += sum(ref.activation for ref in references)
        for name, knowledge in normalized.items():
            normalized[name] = self.penalize_repetition(knowledge)





    @property
    def simple_projection(self):
        if self.items():
            return { name: language.simple_projection for name, language in self.items() }
        elif hasattr(self, '_simple_projection'):
            return self._simple_projection
        else:
            self._version, self._simple_projection = self._load_from_s3()
            return self._simple_projection

    @property
    def s3object(self):
        if hasattr(self, '_s3object'):
            return self._s3object
        else:
            self._s3object = self.bucket.Object('users/{}'.format(self.username))
            setattr(self._s3object, 'getdata', lambda: json.loads(self._s3object.get()['Body'].read().decode()))
            setattr(self._s3object, 'putdata', lambda data: self._s3object.put(Body = json.dumps(data))['ETag'])
            return self._s3object

    def _load_from_s3(self):
        try:
            knowledge = self.s3object.getdata()
            version = knowledge['version'] if 'version' in knowledge else 0
            simple_projection = knowledge['knowledge'] if 'knowledge' in knowledge else knowledge
        except botocore.exceptions.ClientError as exc:
            version = 0
            simple_projection = dict()
        return (version, simple_projection)

    def exists(self):
        try:
            self._version, self._simple_projection = self._load_from_s3()
            return self._version == self.VERSION
        except botocore.exceptions.ClientError as exc:
            return False

    def walk(self, callback):
        for language, modules in self.simple_projection.items():
            for module, knowledge in modules.items():
                callback(language, module, knowledge)

    def save(self, wait_for_consistency = True):
        start = time.time()
        LOGGER.debug('Writing knowledge for user {} to s3'.format(self.username))
        etag = self.s3object.putdata({ 'version': self.VERSION, 'knowledge': self.simple_projection })
        all_objects = { etag: self.s3object }

        def _update_leaderboard_entry(language, module, knowledge):
            prefix = 'leaderboard/{}/{}/{}'.format(language, module, self.username)
            for obj in self.bucket.objects.filter(Prefix = prefix):
                obj.delete()
            key = prefix + ':{:.2f}'.format(knowledge)
            obj = self.bucket.Object(key = key)
            etag = obj.put(Body = bytes('', 'utf-8'))['ETag']
            all_objects[etag] = obj

        self.walk(_update_leaderboard_entry)

        for etag, obj in all_objects.items():
            obj.wait_until_exists(IfMatch = etag)
        LOGGER.debug('Writing knowledge to s3 took {} seconds'.format(time.time() - start))

    def calculate_rankings(self):
        # TODO: modify underlying knowledge model so that we actually have the
        # concept of stdlib and grammar and don't have to use special module names
        rankings = dict()
        for language, modules in self.simple_projection.items():
            rankings[language] = { 'modules': dict() }
            for module, score in modules.items():
                if module == OVERALL_KEY:
                    rankings[language].update(self._get_ranking(language, module, score))
                elif module == STDLIB_KEY:
                    rankings[language]['stdlib'] = self._get_ranking(language, module, score)
                elif module == PRIVATE_KEY:
                    pass
                else:
                    rankings[language]['modules'][module] = self._get_ranking(language, module, score)
        self._write_rankings_to_db(rankings)

    def _get_ranking(self, language, module, score):
        knowledge_regex = re.compile('.*\:([0-9,.]+)')
        key = 'leaderboard/{}/{}/'.format(language, module)
        score = float('{:.2f}'.format(score))

        all_users = []
        for user in self.bucket.objects.filter(Prefix = key):
            knowledge = float(re.match('.*\:([0-9,.]+)', user.key).group(1))
            all_users.append(knowledge)
        all_users = sorted(all_users)

        return {
                'rank': len(all_users) - bisect.bisect(all_users, score),
                'population': len(all_users) + 1,
                'relevance': int(sum(all_users) + score)
                }

    def _write_rankings_to_db(self, rankings):
        with psycopg2.connect(dbname = 'postgres', user = 'postgres', password = '', host = 'database') as connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT id FROM github_user WHERE login = %(github_id)s', {'github_id': self.username})
                github_user_id = cursor.fetchone()[0]
                cursor.execute('SELECT user_id FROM github_account WHERE github_user_id = %(github_user_id)s', {'github_user_id': github_user_id})
                user_id = cursor.fetchone()[0]
                cursor.execute('SELECT id FROM role WHERE user_id = %(user_id)s AND type = %(type)s', {'user_id': user_id, 'type': 'contractor'})
                skill_set_id = cursor.fetchone()[0] # skill_set_id == contractor_id
                cursor.execute('UPDATE skill_set SET skills=%(skills)s WHERE id=%(skill_set_id)s', {'skills': pickle.dumps(rankings), 'skill_set_id': skill_set_id})

class Reference(datetime.date):

    def __new__(cls, date):
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
    person_1.add_reference('python', 'socket', 'recv', date = datetime.date.today(), count = 80)

    person_2 = KnowledgeModel()
    person_2.add_reference('python', 'socket', 'send', date = datetime.date.today(), count = 10)
    person_2.add_reference('python', 'socket', 'recv', date = datetime.date.today(), count = 10)
    person_2.add_reference('python', 'collections', 'defaultdict', date = datetime.date.today(), count = 10)
    person_2.add_reference('python', 'collections', 'Counter', date = datetime.date.today(), count = 10)
    person_2.add_reference('python', 'iterools', 'filterfalse', date = datetime.date.today(), count = 10)
    person_2.add_reference('python', 'functools', 'lru_cache', date = datetime.date.today(), count = 10)
    person_2.add_reference('python', 'functools', 'reduce', date = datetime.date.today(), count = 10)
    person_2.add_reference('python', 'contextlib', 'AbstractContextManager', date = datetime.date.today(), count = 10)

    person_3 = KnowledgeModel()
    person_3.add_reference('python', 'socket', 'recv', date = datetime.date.today() - datetime.timedelta(days=1800), count = 80)

    person_4 = KnowledgeModel()
    person_4.add_reference('python', 'socket', 'recv', date = datetime.date.today() - datetime.timedelta(days=365), count = 80)

    person_5 = KnowledgeModel()
    person_5.add_reference('python', 'socket', 'recv', date = datetime.date.today() - datetime.timedelta(days=2*365), count = 80)

    person_6 = KnowledgeModel()
    person_6.add_reference('python', 'socket', 'recv', date = datetime.date.today() - datetime.timedelta(days=4*365), count = 80)

    print('Person 1\'s knowledge (narrow) looks like {}'.format(person_1.simple_projection))
    print()
    print('Person 1\'s overall knowledge (narrow) is {}'.format(person_1.simple_projection['python'][OVERALL_KEY]))
    print('Person 2\'s overall knowledge (broad) is {}'.format(person_2.simple_projection['python'][OVERALL_KEY]))
    print('Person 3\'s overall knowledge (narrow and a long time ago) is {}'.format(person_3.simple_projection['python'][OVERALL_KEY]))
    print('Person 4\'s overall knowledge (narrow and year ago) is {}'.format(person_4.simple_projection['python'][OVERALL_KEY]))
    print('Person 5\'s overall knowledge (narrow and two years ago) is {}'.format(person_5.simple_projection['python'][OVERALL_KEY]))
    print('Person 6\'s overall knowledge (narrow and four years ago) is {}'.format(person_6.simple_projection['python'][OVERALL_KEY]))
    print()
    print('Ratio of broad to narrow knowledge in this case is {}'.format(person_2.simple_projection['python'][OVERALL_KEY]/person_1.simple_projection['python'][OVERALL_KEY]))
    print()

    # testing incorrect length references
    person_3.add_reference('python', date = datetime.date.today() - datetime.timedelta(days=1800), count = 1)
    person_3.add_reference('python', 'socket', 'socket', 'recv', date = datetime.date.today() - datetime.timedelta(days=1800), count = 1)
