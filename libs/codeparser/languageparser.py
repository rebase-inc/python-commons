import abc
import json
import base64
import logging

from functools import lru_cache
from collections import Counter

from . import exceptions

LOGGER = logging.getLogger()

class LanguageParser(metaclass = abc.ABCMeta):

    @classmethod
    def _log_callback(cls, *args, date, count):
        LOGGER.debug(*args, date, count)

    def __init__(self, callback = _log_callback):
        self.callback = callback

    @abc.abstractmethod
    def get_context(self, repo_name, commit, path):
        return { 'path': path, 'url': self.get_commit_url_path(repo_name, commit, path) }

    def parse(self, code, context = None):
        request = json.dumps(
            {
                'code':     base64.b64encode(code).decode('utf-8'),
                'context':  context
            }
        )
        for index, parser in enumerate(self.parsers):
            response = parser.send(request)
            if response and 'error' not in response:
                break
        else:
            raise exceptions.UnparsableCode(self.language, context['url'], response['error'] if response else None)
        self.parsers.insert(0, self.parsers.pop(index))
        return response

    def close(self):
        self.relevance_checker.close()
        for parser in self.parsers:
            parser.close()

    @lru_cache()
    def get_module_counts(self, repo_name, commit, path):
        code = commit.tree[path].data_stream.read()
        context = self.get_context(repo_name, commit, path)
        use_count = self.parse(code, context)['use_count']
        return Counter({ name: count for name, count in use_count.items() if self.check_relevance(name) })

    def get_commit_url_path(self, repo_name, commit, path):
        return 'https://github.com/{fullname}/blob/{hexsha}/{path}'.format(fullname = repo_name, hexsha = commit.hexsha, path = path)

    @property
    @abc.abstractmethod
    def relevance_checker(self):
        pass

    @abc.abstractmethod
    def check_relevance(self, module):
        if module.split('.')[0] == '__stdlib__':
            return True
        elif module.split('.')[0] == '__private__':
            return False
        else:
            relevance = int(self.relevance_checker.send(json.dumps({ 'module': module.split('.')[0] }))['impact'])
            return bool(relevance > 0)

    def analyze_blob(self, repo_name, commit, path):
        module_counts = self.get_module_counts(repo_name, commit, path)
        for module, count in module_counts.most_common():
            self.callback(self.language, *module.split('.'), date = commit.authored_datetime, count = count)

    def analyze_diff(self, repo_name, commit, diff):
        counts_before = self.get_module_counts(repo_name, commit.parents[0], diff.a_path)
        counts_after = self.get_module_counts(repo_name, commit, diff.b_path)
        differential_counts = counts_before
        differential_counts.subtract(counts_after)
        for module, differential_count in differential_counts.most_common():
            if not differential_count:
                continue
            self.callback(self.language, *module.split('.'), date = commit.authored_datetime, count = abs(differential_count))
