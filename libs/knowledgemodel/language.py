import os
import json
import base64
import socket
import logging

from collections import defaultdict, Counter
from functools import lru_cache
from asynctcp import BlockingTcpClient

import git

LOGGER = logging.getLogger()

class LanguageKnowledge(object):

    def __init__(
        self,
        name,
        private_namespace_generator,
        standard_library_namespace_generator,
        grammar_namespace_generator,
        old_format=False
    ):
        self.grammar_use = defaultdict(list)
        self.private_module_use = defaultdict(list)
        self.standard_module_use = defaultdict(list)
        self.external_module_use = defaultdict(list)
        self.name = name
        self.private_namespace_generator = private_namespace_generator
        self.standard_library_namespace = standard_library_namespace_generator()
        self.grammar_namespace = grammar_namespace_generator()
        self.old_format = old_format
        self.parser_client = None
        self.impact_client = None

    def parse_code(self, code):
        if not code:
            return Counter()
        response = self.parser_client.send(json.dumps({ 'code': base64.b64encode(code).decode('utf-8') }))
        return Counter(response['use_count'])

    def get_impact(self, module):
        if not module:
            return 0
        module = module.split('.')[0]
        try:
            response = self.impact_client.send(json.dumps({ 'module': module }))
        except socket.timeout as exc:
            LOGGER.error('Returning fake impact score of 1, because impact client timed out')
            return 1
        return int(response['impact'])

    @lru_cache()
    def get_private_namespace(self, tree):
        return self.private_namespace_generator(tree)

    def add_knowledge_data(self, authored_datetime, private_namespace, use_before, use_after):
        if self.old_format:
            return self._old_format_add_knowledge_data(authored_datetime, private_namespace, use_before, use_after)

        for module in (use_before | use_after):
            module = module.split('.')[0]

            use_delta = abs(use_before[module] - use_after[module])
            if not use_delta: continue
            timestamps = [ authored_datetime.toordinal() for _ in range(use_delta) ]

            if module in private_namespace:
                self.private_module_use[module] += timestamps

            elif module in grammar_namespace:
                self.grammar_use[module] += timestamps

            elif module in self.standard_library_namespace:
                self.standard_module_use[module] += timestamps

            elif module in self.external_module_use or self.get_impact(module) > 0:
                self.external_module_use[module] += timestamps

    def _old_format_add_knowledge_data(self, authored_datetime, private_namespace, use_before, use_after):
        for module in (use_before | use_after):
            use_delta = abs(use_before[module] - use_after[module])
            if not use_delta: continue

            if module.startswith('0.'):
                module = module.replace('0.', '').split('.')[0]
                self.private_module_use[module] += [ authored_datetime for _ in range(use_delta) ]

            elif module.startswith('1.'):
                module = module.replace('1.', '').split('.')[0]
                self.standard_module_use[module] += [ authored_datetime for _ in range(use_delta) ]

            elif module.startswith('2.') or self.get_impact(module.replace('2.', '').split('.')[0]):
                module = module.replace('2.', '').split('.')[0]
                self.external_module_use[module] += [ authored_datetime for _ in range(use_delta) ]

    def analyze_diff(self, diff, commit):
        _namespace_before = self.get_private_namespace(commit.parents[0].tree)
        private_namespace = _namespace_before.union(self.get_private_namespace(commit.tree))

        use_before = self.parse_code(commit.parents[0].tree[diff.a_path].data_stream.read() if not diff.new_file else None)
        use_after = self.parse_code(commit.tree[diff.b_path].data_stream.read() if not diff.deleted_file else None)
        self.add_knowledge_data(commit.authored_datetime, private_namespace, use_before, use_after)

    def analyze_blob(self, blob, commit):
        private_namespace = self.get_private_namespace(commit.tree)

        use_before = self.parse_code(None)
        use_after = self.parse_code(commit.tree[blob.path].data_stream.read())
        self.add_knowledge_data(commit.authored_datetime, private_namespace, use_before, use_after)


class GrammarNamespace(object):

    def __contains__(self, module):
        return module.startswith('__grammar__')


class PythonKnowledge(LanguageKnowledge):
    NAME = 'python'

    def __init__(self):
        super().__init__(
            self.NAME,
            lambda tree: self.get_python_module_names(tree, tree),
            self.get_python_standard_library_names,
            GrammarNamespace,
        )
        self.parser_client = BlockingTcpClient('python_parser', 25252, timeout = 60)
        self.impact_client = BlockingTcpClient('python_impact', 25000, timeout = 3)

    def get_python_module_names(self, tree, base_tree):
        known_modules = set()
        if not tree:
            return known_modules
        for entry in tree:
            try:
                if isinstance(entry, git.Tree):
                    new_modules = self.get_python_module_names(entry, base_tree)
                    known_modules.update(new_modules)
                elif isinstance(entry, git.Submodule):
                    LOGGER.debug('Skipping submodule')
                elif entry.name == '__init__.py':
                    path_relative_to_repo = entry.path.replace(base_tree.path, '')
                    module_name = os.path.dirname(path_relative_to_repo).replace('/', '.')
                    known_modules.add(module_name)
            except Exception as exc:
                LOGGER.error('Unhandled exception in git tree traversal: {}'.format(str(exc)))
        return known_modules

    @classmethod
    def get_python_standard_library_names(cls):
        from stdlib_list import stdlib_list, long_versions
        known_standard_library_modules = set()
        for version in long_versions:
            known_standard_library_modules = known_standard_library_modules.union(set(stdlib_list(version)))
        return known_standard_library_modules


class JavascriptKnowledge(LanguageKnowledge):

    NAME = 'javascript'

    def __init__(self):
        super().__init__(
            self.NAME,
            lambda tree: set(),
            self.get_javascript_standard_library_names,
            GrammarNamespace,
        )
        self.parser_client = BlockingTcpClient('javascript_parser', 7777, timeout = 60)
        self.impact_client = BlockingTcpClient('javascript_impact', 9999, timeout = 3)

    @classmethod
    def get_javascript_standard_library_names(cls):
        return set([ 'Infinity', 'NaN', 'undefined', 'null', 'eval', 'isFinite', 'isNaN', 'parseFloat',
            'parseInt', 'decodeURI', 'decodeURIComponent', 'encodeURI', 'encodeURIComponent', 'escape',
            'unescape', 'Object', 'Function', 'Boolean', 'Symbol', 'Error', 'EvalError', 'InternalError',
            'RangeError', 'ReferenceError', 'SyntaxError', 'TypeError', 'URIError', 'Number', 'Math',
            'Date', 'String', 'RegExp', 'Array', 'Int8Array', 'Uint8Array', 'Uint8ClampedArray',
            'Int16Array', 'Int16Array', 'Uint16Array', 'Int32Array', 'Uint32Array', 'Float32Array',
            'Float64Array', 'Map', 'Set', 'WeakMap', 'WeakSet', 'SIMD', 'SIMD.Float32x4', 'SIMD.Float64x2',
            'SIMD.Int8x16', 'SIMD.Int16x8', 'SIMD.Int32x4', 'SIMD.Uint8x16', 'SIMD.Uint16x8', 'SIMD.Uint32x4',
            'SIMD.Bool8x16', 'SIMD.Bool16x8', 'SIMD.Bool32x4', 'SIMD.Bool64x2', 'ArrayBuffer', 'SharedArrayBuffer',
            'Atomics', 'DataView', 'JSON', 'Promise', 'Generator', 'GeneratorFunction', 'Reflect', 'Proxy',
            'Intl', 'Intl.Collator', 'Intl.DateTimeFormat', 'Intl.NumberFormat', 'arguments' ])


