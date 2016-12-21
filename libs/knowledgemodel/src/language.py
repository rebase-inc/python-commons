import os
import json
import base64
import logging
from socket import socket, SHUT_RDWR

from collections import defaultdict, Counter
from functools import lru_cache

import git

LOGGER = logging.getLogger()

# this is copied over from asynctcp library
class BlockingTCPClient(object):
    def __init__(self, host = 'localhost', port = 25252, encode = lambda d: d, decode = lambda d: d):
        self.socket = socket()
        self.encode = encode
        self.decode = decode

        self.read_stream = self.socket.makefile(mode = 'rb')
        self.write_stream = self.socket.makefile(mode = 'wb')

        self.socket.connect((host, port))

    def close(self):
        self.socket.shutdown(SHUT_RDWR)
        self.socket.close()

    def send(self, data):
        self.write_stream.write(self.encode(data))
        self.write_stream.flush()
        return self.decode(self.socket.recv(10000))

class LanguageKnowledge(object):

    def __init__(self, name, private_namespace_generator, standard_library_namespace_generator, old_format = False):
        self.private_module_use = defaultdict(list)
        self.standard_module_use = defaultdict(list)
        self.external_module_use = defaultdict(list)

        self.name = name
        self.private_namespace_generator = private_namespace_generator
        self.standard_library_namespace = standard_library_namespace_generator()
        self.old_format = old_format
        self.parser_client = None
        self.impact_client = None

    def parse_code(self, code):
        if not code:
            return Counter()
        use_dict = self.parser_client.send(code)
        return Counter(json.loads(use_dict))

    def get_impact(self, name):
        if not name:
            return 0
        name = bytes(name.split('.')[0], 'utf-8')
        return int(self.impact_client.send(name))

    @lru_cache()
    def get_private_namespace(self, tree):
        return self.private_namespace_generator(tree)

    def add_knowledge_data(self, authored_datetime, private_namespace, use_before, use_after):
        if self.old_format:
            return self._old_format_add_knowledge_data(authored_datetime, private_namespace, use_before, use_after, allow_unrecognized)

        for module in (use_before | use_after):
            use_delta = abs(use_before[module] - use_after[module])
            if not use_delta: continue

            if next(filter(lambda m: module.startswith(m), private_namespace), False):
                self.private_module_use[module] += [ authored_datetime.toordinal() for _ in range(use_delta) ]

            elif next(filter(lambda m: module.startswith(m), self.standard_library_namespace), False):
                self.standard_module_use[module] += [ authored_datetime.toordinal() for _ in range(use_delta) ]

            elif next(filter(lambda m: module.startswith(m), self.external_module_use), False) or self.get_impact(module):
                self.external_module_use[module] += [ authored_datetime.toordinal() for _ in range(use_delta) ]

    def _old_format_add_knowledge_data(self, authored_datetime, private_namespace, use_before, use_after, allow_unrecognized = True):
        for module in (use_before | use_after):
            use_delta = abs(use_before[module] - use_after[module])
            if not use_delta: continue

            if module.startswith('0.'):
                module = module.replace('0.', '')
                self.private_module_use[module] += [ authored_datetime for _ in range(use_delta) ]

            elif module.startswith('1.'):
                module = module.replace('1.', '')
                self.standard_module_use[module] += [ authored_datetime for _ in range(use_delta) ]

            elif allow_unrecognized or module.startswith('2.'):
                module = module.replace('2.', '')
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

class PythonKnowledge(LanguageKnowledge):
    NAME = 'python'

    def __init__(self):
        super().__init__(self.NAME, lambda tree: self.get_python_module_names(tree, tree), self.get_python_standard_library_names)
        self.parser_client = BlockingTCPClient('python_parser', 25252, encode = lambda d: base64.b64encode(d) + bytes('\n', 'utf-8'), decode = lambda d: d.decode())
        self.impact_client = BlockingTCPClient('python_impact', 25000, encode = lambda d: base64.b64encode(d) + bytes('\n', 'utf-8'), decode = lambda d: d.decode())

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
        super().__init__(self.NAME, lambda tree: set(), self.get_javascript_standard_library_names)
        self.parser_client = BlockingTCPClient('javascript_parser', 7777, encode = lambda d: base64.b64encode(d) + bytes('\n', 'utf-8'), decode = lambda d: d.decode())
        self.impact_client = BlockingTCPClient('javascript_impact', 9999, encode = lambda d: base64.b64encode(d) + bytes('\n', 'utf-8'), decode = lambda d: d.decode())

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

