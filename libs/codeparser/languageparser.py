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
    def get_context(self, tree, path):
        return dict()

    def parse(self, code, context = None):
        for index, parser in enumerate(self.parsers):
            response = parser.send(json.dumps({ 'code': base64.b64encode(code).decode('utf-8'), 'context': context }))
            if response and 'error' not in response:
                break
        else:
            raise exceptions.UnparsableCode(self.language)
        # always try the last successful parser first on the next round
        self.parsers.insert(0, self.parsers.pop(index))
        return response

    def close(self):
        self.relevance_checker.close()
        for parser in self.parsers:
            parser.close()

    def get_module_counts(self, tree, path):
        if not tree or not path:
            return None
        context = self.get_context(tree, path)
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

    def analyze_code(self, tree_before, tree_after, path_before, path_after, authored_at):
        module_counts_before = Counter(self.get_module_counts(tree_before, path_before))
        module_counts_after = Counter(self.get_module_counts(tree_after, path_after))
        differential_counts = module_counts_before
        differential_counts.subtract(module_counts_after)
        for module, differential_count in differential_counts.most_common():
            if not differential_count:
                continue
            self.callback(self.language, *module.split('.'), date = authored_at, count = abs(differential_count))
