import os
import re
import json
import time
import bisect
import logging
import datetime

import boto3
import botocore

from . import Population, Ranking, Knowledge

logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('botocore').setLevel(logging.WARNING)

LOGGER = logging.getLogger()


class S3Config(dict):
    def __init__(self, region_name = None, aws_access_key_id = None, aws_secret_access_key = None):
        self['region_name'] = region_name or os.environ['AWS_REGION']
        self['aws_access_key_id'] = aws_access_key_id or os.environ['AWS_ACCESS_KEY_ID']
        self['aws_secret_access_key'] = aws_secret_access_key or os.environ['AWS_SECRET_ACCESS_KEY']


class S3Population(Population):

    def __init__(self, bucket: str, config: dict = None, depth: int = 2):
        self.bucket_name = bucket
        self.config = S3Config(**config or {})
        self.depth = depth
        self.knowledge_prefix = 'leaderboard/' + (depth * '{}/')
        self.user_key = 'users/{}'
        self.knowledge_regex = re.compile('.*\:([0-9,.]+)')

    @property
    def bucket(self):
        if not hasattr(self, '_bucket'):
            self._bucket = boto3.resource('s3', **self.config).Bucket(self.bucket_name)
        return self._bucket

    def calculate_rankings(self, knowledge):
        rankings = dict()
        for name, score in knowledge.items():
            rankings[name] = self._calculate_ranking(score, *name.split('.'))
        return rankings

    def _calculate_ranking(self, score, *name):
        if len(name) != self.depth:
            raise Exception('Name must have exactly {} components'.format(self.depth))

        target_population = []
        for knowledge in self.bucket.objects.filter(Prefix = self.knowledge_prefix.format(*name)):
            target_population.append(float(self.knowledge_regex.match(knowledge.key).group(1)))
        target_population = sorted(target_population)

        return Ranking(target_population, score)

    def add_user_knowledge(self, username, knowledge):
        if not isinstance(knowledge, Knowledge):
            raise TypeError('Cant convert {} to {}'.format(type(knowledge), Knowledge.__name__))
        LOGGER.debug('Writing knowledge for user {} to s3'.format(username))

        version = knowledge.version
        user_hash = knowledge.user_hash
        knowledge = knowledge.normalize(depth = self.depth)

        start = time.time()
        obj = self.bucket.Object(self.user_key.format(username))
        etag = obj.put(Body = json.dumps(dict(user_hash = user_hash, version = version, knowledge = knowledge)))['ETag']
        all_objects = { etag: obj }

        for name, score in knowledge.items():
            prefix = self.knowledge_prefix.format(*name.split('.')) + username
            for obj in self.bucket.objects.filter(Prefix = prefix):
                obj.delete()
            obj = self.bucket.Object(key = prefix + ':{:.2f}'.format(score))
            etag = obj.put(Body = b'')['ETag']
            all_objects[etag] = obj

        for etag, obj in all_objects.items():
            obj.wait_until_exists(IfMatch = etag)
        LOGGER.debug('Writing knowledge to s3 took {} seconds'.format(time.time() - start))

    def get_user_knowledge(self, username):
        try:
            body = json.loads(self.bucket.Object(self.user_key.format(username)).get()['Body'].read().decode())
            user_hash = body['user_hash'] if 'user_hash' in body else None
            return Knowledge(user_hash, version = body['version'], **body['knowledge'])
        except botocore.exceptions.ClientError:
            return None

    def add_user_ranking(self, username, ranking):
        raise NotImplementedError()

    def user_ranking_exists(self, username, version = None):
        return False

if __name__ == '__main__':
    population = S3Population(os.environ['S3_KNOWLEDGE_BUCKET'])
    print('User knowledge {} exist'.format('does' if population.get_user_knowledge('andrewmillspaugh') else 'doesn\'t'))
    ranking = population._calculate_ranking(10.2, 'javascript', 'react')
    print('Percentile for javascript.react knowledge of 10.2 is top {:.2%}'.format(ranking.rank / ranking.population))
    k = Knowledge('fakehash')
    print('Can we test knowledge equality? {}'.format('yes' if k == k else 'no'))
    k.add_reference('python', 'socket', 'recv', date = datetime.date.today(), count = 5)
    k.add_reference('python', 'socket', 'send', date = datetime.date.today(), count = 5)
    population.add_user_knowledge('somefakedude', k)
    print('Can we load the knowledge we just wrote?')
    print(population.get_user_knowledge('somefakedude'))
