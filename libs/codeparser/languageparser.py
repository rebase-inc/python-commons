import abc
import json
import base64
import logging

from collections import Counter

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

    @property
    @abc.abstractmethod
    def remote_parser(self):
        pass

    @abc.abstractmethod
    def close(self):
        self.remote_parser.close()
        self.relevance_checker.close()

    @abc.abstractmethod
    def get_module_counts(self, tree, path):
        if not tree or not path:
            return None
        context = self.get_context(tree, path)
        code = tree[path].data_stream.read()
        use_count = self.remote_parser.send(json.dumps({ 'code': base64.b64encode(code).decode('utf-8'), 'context': context }))['use_count']
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
            print(self.language, *module.split('.'), authored_at, abs(differential_count))
            self.callback(self.language, *module.split('.'), date = authored_at, count = abs(differential_count))
