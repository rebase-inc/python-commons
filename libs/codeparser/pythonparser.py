from functools import reduce

from asynctcp import BlockingTcpClient

from . import LanguageParser

PY3_HOST = 'python_parser'
PY3_PORT = 25252
PY2_HOST = 'python_2_parser'
PY2_PORT = 25253
IMPACT_HOST = 'python_impact'
IMPACT_PORT = 25000


class PythonParser(LanguageParser):
    language = 'python'

    def __init__(self, callback):
        super().__init__(callback)
        self.parsers = []
        self.parsers.append(BlockingTcpClient(PY3_HOST, PY3_PORT, timeout = 60))
        self.parsers.append(BlockingTcpClient(PY2_HOST, PY2_PORT, timeout = 60))

    def get_context(self, repo_name, commit, path):
        return super().get_context(repo_name, commit, path)

    def check_relevance(self, module):
        return super().check_relevance(module)

    @property
    def relevance_checker(self):
        if not hasattr(self, '_relevance_checker'):
            self._relevance_checker = BlockingTcpClient(IMPACT_HOST, IMPACT_PORT, timeout = 60)
        return self._relevance_checker
