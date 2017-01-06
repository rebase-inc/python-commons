import io
import datetime
import unittest
import functools

from collections import defaultdict

from . import CodeParser

class FakeGitBlob(io.BytesIO):
    @property
    def data_stream(self):
        return self

class FakeGitTree(dict):
    def __init__(self, **kwargs):
        super().__init__({ path: FakeGitBlob(bytes(code, 'utf-8')) for path, code in kwargs.items()})

class TestCodeParser(unittest.TestCase):

    @classmethod
    def _append_uses(self, uses, *args, date, count):
        uses['.'.join(args)] = count
    
    def setUp(self):
        self.uses = {}
        self.parser = CodeParser(callback = functools.partial(self._append_uses, self.uses))

    def test_analyze_diff(self):
        tree_before = FakeGitTree(**{'foo.py': 'from unittest import TestCase', 'bar.py': 'from socket import socket'})
        tree_after = FakeGitTree(**{'foo.py': 'from io import StringIO', 'bar.py': 'from socket import socket'})
        self.parser.analyze_code(tree_before, tree_after, 'foo.py', 'foo.py', datetime.date.today())
    
    def tearDown(self):
        self.parser.close()

if __name__ == '__main__':
    unittest.main()
