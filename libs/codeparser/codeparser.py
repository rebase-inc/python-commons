import os
import re
import logging
import mimetypes

from . import PythonParser, JavascriptParser
from . import exceptions
from . import ParserHealth

LOGGER = logging.getLogger()

class CodeParser(object):

    def __init__(self, callback):
        self.parsers = {}
        for parser in [PythonParser, JavascriptParser]:
            self.parsers[parser.language] = parser(callback = callback)
        self.mimetypes = mimetypes.MimeTypes(strict = False)
        self.mimetypes.add_type('application/javascript','.jsx', strict = False)
        self.mimetype_regex = re.compile('(?:application|text)\/(?:(?:x-)?)(?P<language>[a-z]+)$')
        self.health = ParserHealth()

    def guess_language(self, path):
        mimetype = self.mimetypes.guess_type(path)[0] or ''
        match = self.mimetype_regex.match(mimetype)
        if match:
            return match.group('language')
        else:
            raise exceptions.UnrecognizedExtension(os.path.splitext(path)[-1])

    def get_parser(self, path):
        language = self.guess_language(path)
        if language in self.parsers:
            return self.parsers[language]
        else:
            raise exceptions.MissingLanguageSupport(language)

    def analyze_code(self, repo, commit, tree_before, tree_after, path_before, path_after, authored_at):
        with self.health:
            # we're going to assume the language doesn't change during the commit
            self.get_parser(path_before or path_after).analyze_code(repo, commit, tree_before, tree_after, path_before, path_after, authored_at)

    def close(self):
        for parser in self.parsers.values():
            parser.close()
