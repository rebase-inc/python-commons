from functools import reduce

from stdlib_list import stdlib_list, long_versions

from asynctcp import BlockingTcpClient

from . import LanguageParser

PY3_HOST = 'python_parser'
PY3_PORT = 25252
PY2_HOST = 'python_2_parser'
PY2_PORT = 25253
IMPACT_HOST = 'python_impact'
IMPACT_PORT = 25000


class StdLib(set):

    def __contains__(self, module):
        return module.startswith('__grammar__') or super().__contains__(module)


class PythonParser(LanguageParser):
    language = 'python'
    stdlib = StdLib(reduce(lambda namespace, version: namespace.union(set(stdlib_list(version))), long_versions, set()))

    def __init__(self, callback):
        super().__init__(callback)
        self.parsers = []
        self.parsers.append(BlockingTcpClient(PY3_HOST, PY3_PORT, timeout = 60))
        self.parsers.append(BlockingTcpClient(PY2_HOST, PY2_PORT, timeout = 60))

    def get_context(self, commit, path):
        # skipping the context for now, because if something isn't standard library and
        # it isn't found to be "relevant", we're not going to include it. However, this
        # may be useful in the future for things like understanding references.
        return super().get_context(commit, path)

    def check_relevance(self, module):
        return module.split('.')[0] in self.stdlib or super().check_relevance(module)

    @property
    def relevance_checker(self):
        if not hasattr(self, '_relevance_checker'):
            self._relevance_checker = BlockingTcpClient(IMPACT_HOST, IMPACT_PORT, timeout = 60)
        return self._relevance_checker
