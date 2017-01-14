from asynctcp import BlockingTcpClient

from . import LanguageParser

PARSER_HOST = 'javascript_parser'
PARSER_PORT = 7777
IMPACT_HOST = 'javascript_impact'
IMPACT_PORT = 9999
STDLIB = set(module.split('.')[0] for module in [
    'Infinity', 'NaN', 'undefined', 'null', 'eval', 'isFinite', 'isNaN', 'parseFloat',
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

class JavascriptParser(LanguageParser):
    language = 'javascript'
    stdlib = STDLIB

    def __init__(self, callback):
        super().__init__(callback)
        self.parsers = []
        self.parsers.append(BlockingTcpClient(PARSER_HOST, PARSER_PORT, timeout = 60))

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
