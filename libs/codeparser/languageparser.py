import abc
import json
import base64
import logging

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
    def get_context(self, repo, commit, tree, path, before):
        return {
            'repo': repo.html_url,
            'commit': commit.hexsha,
            'tree': tree.hexsha,
            'order': 'BEFORE' if before else 'AFTER',
            'path': path
        }

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
        if response and 'error' in response:
            raise exceptions.UnparsableCode(context, self.language)
        if index:
            LOGGER.debug('Switched to parser: %s', parser.host)
            # always try the last successful parser first on the next round
            self.parsers.insert(0, self.parsers.pop(index))
        return response

    def close(self):
        self.relevance_checker.close()
        for parser in self.parsers:
            parser.close()

    def get_module_counts(self, repo, commit, tree, path, before):
        if not tree or not path:
            return None
        context = self.get_context(repo, commit, tree, path, before)
        code = tree[path].data_stream.read()
        use_count = self.parse(code, context)['use_count']
        return { name: count for name, count in use_count.items() if self.check_relevance(name) }

    @property
    @abc.abstractmethod
    def relevance_checker(self):
        pass

    @abc.abstractmethod
    def check_relevance(self, module):
        return int(self.relevance_checker.send(json.dumps({ 'module': module.split('.')[0] }))['impact']) > 0

    def analyze_code(self, repo, commit, tree_before, tree_after, path_before, path_after, authored_at):
        module_counts_before = Counter(self.get_module_counts(repo, commit, tree_before, path_before, True))
        module_counts_after = Counter(self.get_module_counts(repo, commit, tree_after, path_after, False))
        differential_counts = module_counts_before
        differential_counts.subtract(module_counts_after)
        for module, differential_count in differential_counts.most_common():
            if not differential_count:
                continue
            self.callback(self.language, *module.split('.'), date = authored_at, count = abs(differential_count))
