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

# knowledge = OverallKnowledge()
# parser = CodeParser(add_reference = knowledge.add_reference)
# crawler = GithubCommitCrawler(callback = parser.analyze_code)

class CodeParser(object):
    def __init__(self, add_reference):
        self.parsers = {}
        for parser in [PythonParser, JavaScriptParser]:
            self.parsers[parser.language] = parser(add_reference = add_reference)
        self.mimetypes = mimetypes.MimeTypes(strict = False)
        self.mimetypes.types_map[0]['.jsx'] = self.mimetypes.types_map[1]['.js']
        self.mimetype_regex = re.compile('(?:application|text)\/(?:(?:x-)?)(?P<language>[a-z]+)')

    def parser(self, path):
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
        self.parser(path_before or path_after).analyze_code(tree_before, tree_after, path_before, path_after, authored_at)


