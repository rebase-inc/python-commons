from functools import reduce

from asynctcp import BlockingTcpClient
from stdlib_list import stdlib_list, long_versions

from . import LanguageParser

PARSER_HOST = 'python_parser'
PARSER_PORT = 25252
IMPACT_HOST = 'python_impact'
IMPACT_PORT = 25000

class PythonParser(LanguageParser):
    language = 'python'
    stdlib = reduce(lambda namespace, version: namespace.union(set(stdlib_list(version))), long_versions, set())

    def get_context(self, tree, path):
        # skipping the context for now, because if something isn't standard library and
        # it isn't found to be "relevant", we're not going to include it. However, this
        # may be useful in the future for things like understanding references.
        return super().get_context(tree, path)

    @property
    def remote_parser(self):
        if not hasattr(self, '_parser'):
            self._parser = BlockingTcpClient(PARSER_HOST, PARSER_PORT, timeout = 60)
        return self._parser

    def close(self):
        super().close()

    def get_module_counts(self, tree, path):
        return super().get_module_counts(tree, path)

    def check_relevance(self, module):
        return module.split('.')[0] in self.stdlib or super().check_relevance(module)

    @property
    def relevance_checker(self):
        if not hasattr(self, '_relevance_checker'):
            self._relevance_checker = BlockingTcpClient(IMPACT_HOST, IMPACT_PORT, timeout = 60)
        return self._relevance_checker
