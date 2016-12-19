import re
import logging
import datetime
import mimetypes

from math import exp
from functools import reduce
from collections import defaultdict

from .language import PythonKnowledge, JavascriptKnowledge

LOGGER = logging.getLogger()

class DeveloperProfile(object):
    def __init__(self):
        self.languages = {}
        self.languages[PythonKnowledge.NAME] = PythonKnowledge()
        self.languages[JavascriptKnowledge.NAME] = JavascriptKnowledge()

        self.mimetypes = mimetypes.MimeTypes(strict = False)
        self.mimetypes.types_map[0]['.jsx'] = self.mimetypes.types_map[1]['.js']
        self.mimetype_regex = re.compile('(?:application|text)\/(?:(?:x-)?)(?P<language>[a-z]+)')

    @classmethod
    def _activation(cls, ordinal_date):
        # sigmoidal activation function that weights a commit based on the date it was committed
        number_of_days_ago = ordinal_date - datetime.datetime.now().toordinal()
        return (1 - exp(-4 - number_of_days_ago/400))

    def get_computed_knowledge(self):
        knowledge_metrics = dict()

        for language, knowledge in self.languages.items():
            knowledge_metrics[language] = defaultdict(float)

            for module, dates in knowledge.standard_module_use.items():
                knowledge_metrics[language]['standard_library'] += reduce(lambda prev, curr: prev + self._activation(curr), dates, 0.0)

            for module, dates in knowledge.external_module_use.items():
                module = module.split('.')[0]
                knowledge_metrics[language][module] += reduce(lambda prev, curr: prev + self._activation(curr), dates, 0.0)

        return knowledge_metrics

    def guess_language(self, path):
        # For now, this returns a set with zero or one elements.
        # However, we may in the future support languages that can
        # Be parsed by multiple intepreters, so this returns a set
        mimetype, encoding = self.mimetypes.guess_type(path)
        if not mimetype:
            LOGGER.debug('Unrecognized file type at {}'.format(path))
            return set()
        else:
            match = self.mimetype_regex.match(mimetype)
            if not match:
                LOGGER.debug('Unrecognized mimetype of path {}'.format(path))
                return set()
            return set([ match.group('language') ])

    def analyze_commit(self, commit):
        if len(commit.parents) == 0:
            return self.analyze_initial_commit(commit)
        elif len(commit.parents) == 1:
            return self.analyze_regular_commit(commit)
        else:
            return self.analyze_merge_commit(commit)

    def analyze_regular_commit(self, commit):
        for diff in commit.parents[0].diff(commit, create_patch = True):
            for language in self.guess_language(diff.a_path if diff.deleted_file else diff.b_path):
                if language not in self.languages:
                    LOGGER.debug('Skipping parsing {} in {} due to missing language support'.format(diff.b_path, language))
                    continue
                self.languages[language].analyze_diff(diff, commit)

    def analyze_initial_commit(self, commit):
        for blob in commit.tree.traverse(predicate = lambda item, depth: item.type == 'blob'):
            for language in self.guess_language(blob.path):
                if language not in self.languages:
                    LOGGER.debug('Skipping parsing {} in {} due to missing language support'.format(blob.path, language))
                    continue
                self.languages[language].analyze_blob(blob, commit)

    def analyze_merge_commit(self, commit):
        LOGGER.debug('Skipping merge commit')
