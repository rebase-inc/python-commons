import pickle
import logging
import psycopg2
import functools
import collections

from . import Population
from . import Ranking

class NestedDefaultDict(collections.defaultdict):

    def __init__(self, depth = 2, leaf_factory = float):
        self.depth = depth
        nested = functools.partial(leaf_factory)
        for _ in range(self.depth - 1):
            nested = functools.partial(collections.defaultdict, nested)
        super().__init__(nested)

    def set_item(self, keys, value):
        dic = self
        for key in keys[:-1]:
            dic = dic[key]
        dic[keys[-1]] = value


class PostgresPopulation(Population):

    def __init__(self, dbname = 'postgres', dbuser = 'postgres', dbpassword = '', dbhost = 'database', depth = 2):
        self.dbname = dbname
        self.dbuser = dbuser
        self.dbpassword = dbpassword
        self.dbhost = dbhost
        self.depth = depth

    def calculate_rankings(self, knowledge, *name):
        raise NotImplementedError()

    def add_user_knowledge(self, username, knowledge):
        raise NotImplementedError()

    def user_knowledge_exists(self, username, version = None):
        raise NotImplementedError()

    def user_ranking_exists(self, username, version = None):
        raise NotImplementedError()

    def get_user_knowledge(self, username):
        raise NotImplementedError()

    def add_user_ranking(self, username, ranking):
        nested = NestedDefaultDict(depth = self.depth, leaf_factory = float)
        for name, knowledge in ranking.items():
            nested.set_item(name.split('.'), knowledge)
        with psycopg2.connect(dbname = self.dbname, user = self.dbuser, password = self.dbpassword, host = self.dbhost) as connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT id FROM github_user WHERE login = %(github_id)s', {'github_id': self.username})
                github_user_id = cursor.fetchone()[0]
                cursor.execute('SELECT user_id FROM github_account WHERE github_user_id = %(github_user_id)s', {'github_user_id': github_user_id})
                user_id = cursor.fetchone()[0]
                cursor.execute('SELECT id FROM role WHERE user_id = %(user_id)s AND type = %(type)s', {'user_id': user_id, 'type': 'contractor'})
                skill_set_id = cursor.fetchone()[0] # skill_set_id == contractor_id
                cursor.execute('UPDATE skill_set SET skills=%(skills)s WHERE id=%(skill_set_id)s', {'skills': pickle.dumps(nested), 'skill_set_id': skill_set_id})

if __name__ == '__main__':
    population = PostgresPopulation()
    population.add_user_ranking('SOMEFAKEGUY', {'python.flask': Ranking([1,2,3], 1), 'python.sqlalchemy': Ranking([1,2,3,4], 3) })
