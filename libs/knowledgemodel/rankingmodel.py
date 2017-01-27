import bisect

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
