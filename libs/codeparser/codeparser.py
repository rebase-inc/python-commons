import re
import time
import logging
import datetime
import mimetypes

from math import exp
from functools import reduce
from collections import defaultdict

from . import PythonParser, JavascriptParser

LOGGER = logging.getLogger()

class CodeParser(object):

    @classmethod
    def _log_callback(cls, *args, date, count):
        LOGGER.debug(*args, date, count)

    def __init__(self, callback = _log_callback):
        self.parsers = {}
        for parser in [PythonParser, JavascriptParser]:
            self.parsers[parser.language] = parser(callback = callback)
        self.mimetypes = mimetypes.MimeTypes(strict = False)
        self.mimetypes.types_map[0]['.jsx'] = self.mimetypes.types_map[1]['.js']
        self.mimetype_regex = re.compile('(?:application|text)\/(?:(?:x-)?)(?P<language>[a-z]+)')

    def get_parser(self, path):
        mimetype, encoding = self.mimetypes.guess_type(path)
        if not mimetype:
            LOGGER.debug('Unrecognized file type at {}'.format(path))
            return None
        else:
            match = self.mimetype_regex.match(mimetype)
            if match and match.group('language') in self.parsers:
                return self.parsers[match.group('language')]
            elif match:
                LOGGER.debug('Skipping parsing {} because of missing language support'.format(match.group('language')))
            else:
                LOGGER.debug('Unrecognized mimetype of file {}'.format(path))

    def analyze_code(self, tree_before, tree_after, path_before, path_after, authored_at):
        # we're going to assume the language doesn't change during the commit
        parser = self.get_parser(path_before or path_after)
        if parser:
            parser.analyze_code(tree_before, tree_after, path_before, path_after, authored_at)

    def close(self):
        for parser in self.parsers.values():
            parser.close()
