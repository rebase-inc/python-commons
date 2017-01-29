import bisect
import itertools
import functools
import collections


class NestedKnowledgeRanking(collections.defaultdict):
    '''
    Converts { 'python.socket': {'rank': 0}, 'python.__overall__': {'rank': 1} }
    to       { 'python': { 'rank': 1, 'modules': { 'socket': {'rank': 0 } } } }
    '''

    def __init__(self, knowledge_depth = 2, leaf_factory = float):
        self.knowledge_depth = knowledge_depth
        nested = functools.partial(leaf_factory)
        for _ in range(2 * self.knowledge_depth - 1):
            nested = functools.partial(collections.defaultdict, nested)
        super().__init__(nested)

    def set_item(self, keys, value):
        dic = self
        keys = [ key for key in keys if key != '__overall__' ]
        if len(keys) > self.knowledge_depth:
            raise ValueError('Cant project {} to a nested dict of depth {}'.format('.'.join(keys), self.knowledge_depth))
        keys = list(itertools.chain.from_iterable(zip(keys, ['modules'] * len(keys))))[:-1]
        for key in keys[:-1]:
            dic = dic[key]
        if isinstance(value, dict):
            dic[keys[-1]].update(value)
        else:
            dic[keys[-1]] = value

    @classmethod
    def _to_dict(cls, nested):
        if isinstance(nested, dict):
            return { key: cls._to_dict(val) for key, val in nested.items() }
        else:
            return nested

    def to_dict(self):
        return self._to_dict(self)


class Ranking(dict):
    def __init__(self, population_scores, score, precision = 2):
        super().__init__()
        population_scores = sorted(round(s, precision) for s in population_scores)
        self['rank'] = len(population_scores) - bisect.bisect(population_scores, round(score, precision))
        self['population'] = len(population_scores)
        self['relevance'] = int(sum(population_scores) + score)

    @property
    def rank(self):
        return self['rank']

    @property
    def population(self):
        return self['population']

    @property
    def relevance(self):
        return self['relevance']

if __name__ == '__main__':
    flat = {
        'python.foo.__overall__': Ranking([1,2,3,4], 1),
        'python.__overall__': Ranking([1,2,2,2,3,4], 3)
    }
    nested = NestedKnowledgeRanking(knowledge_depth = 2, leaf_factory = float)
    for name, knowledge in flat.items():
        nested.set_item(name.split('.'), knowledge)
    import json
    print(json.dumps(nested.to_dict()))
