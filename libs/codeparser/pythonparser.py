import os
import logging
from functools import reduce, lru_cache

from asynctcp import BlockingTcpClient

from . import LanguageParser

PY3_HOST = 'python_parser'
PY3_PORT = 25252
PY2_HOST = 'python_2_parser'
PY2_PORT = 25253
IMPACT_HOST = 'python_impact'
IMPACT_PORT = 25000

LOGGER = logging.getLogger()


class PythonParser(LanguageParser):
    language = 'python'

    def __init__(self, callback):
        super().__init__(callback)
        self.parsers = []
        self.parsers.append(BlockingTcpClient(PY3_HOST, PY3_PORT, timeout = 60))
        self.parsers.append(BlockingTcpClient(PY2_HOST, PY2_PORT, timeout = 60))

    def _relative_module_name(self, current_path, module_path):
        # TODO: Improve so that it provides relative imports as well (e.g. from ..foo import bar)
        relative_name = module_path.replace(os.path.dirname(current_path) + '/', '')
        without_extension = os.path.splitext(relative_name)[0].replace('__init__', '').strip('/')
        importable_name = without_extension.replace('/','.')
        return importable_name or '.'

    def get_context(self, repo_name, commit, path):
        private_modules = self.get_private_modules(commit.tree)
        private_modules = {'private_modules': tuple( self._relative_module_name(path, module) for module in private_modules )}
        return {**super().get_context(repo_name, commit, path), **private_modules }

    @lru_cache()
    def get_private_modules(self, tree):
        # NOTE: be careful about changing the signature of this function because of the lru_cache
        modules = []
        for blob in tree.traverse(predicate = lambda item, depth: item.type == 'blob' and item.path.endswith('.py')):
            modules.append(blob.path)
        return tuple(modules)

    def check_relevance(self, module):
        return super().check_relevance(module)

    @property
    def relevance_checker(self):
        if not hasattr(self, '_relevance_checker'):
            self._relevance_checker = BlockingTcpClient(IMPACT_HOST, IMPACT_PORT, timeout = 60)
        return self._relevance_checker
