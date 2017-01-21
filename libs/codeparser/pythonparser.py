import re
import os
import logging
import itertools
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
        current_module = os.path.dirname(current_path).replace('/','.')
        relative_module = module_path.replace(current_module, '', 1).strip('.')
        return relative_module or '.'

    def get_context(self, repo_name, commit, path):
        private_modules = self.get_private_modules(commit.tree, path)
        return {**super().get_context(repo_name, commit, path), **{'private_modules': private_modules} }

    def get_private_modules(self, tree, from_path):
        # TODO: Clean this up...
        modules = set()
        for blob in tree.traverse(predicate = lambda item, depth: item.type == 'blob' and item.path.endswith('.py')):
            if not blob.path.endswith('__init__.py') and os.path.dirname(blob.path) not in modules:
                continue
            module_path = os.path.dirname(blob.path) if blob.path.endswith('__init__.py') else os.path.splitext(blob.path)[0]
            possible_base_paths = itertools.accumulate(module_path.split('/'), os.path.join)
            base_path = (list(itertools.takewhile(lambda path: path not in modules, possible_base_paths)) or [''])[0] +'/'
            absolute_path = re.sub('^' + re.escape(base_path), '', os.path.dirname(blob.path)) + '/'
            current_path = re.sub('^' + re.escape(base_path), '', os.path.dirname(from_path)) + '/'
            relative_path = re.sub('^' + re.escape(current_path), '', absolute_path)
            modules.add(absolute_path)
            modules.add(relative_path)
        return sorted(tuple(module.replace('/','.').strip('.') or '.' for module in modules))

    def check_relevance(self, module):
        return super().check_relevance(module)

    @property
    def relevance_checker(self):
        if not hasattr(self, '_relevance_checker'):
            self._relevance_checker = BlockingTcpClient(IMPACT_HOST, IMPACT_PORT, timeout = 60)
        return self._relevance_checker
