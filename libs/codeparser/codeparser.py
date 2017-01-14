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

    def supports_any_of(self, *languages):
        return bool(set(self.parsers.keys()) & set(lang.lower() for lang in languages))

    def get_parser(self, path):
        language = self.guess_language(path)
        if language in self.parsers:
            return self.parsers[language]
        else:
            raise exceptions.MissingLanguageSupport(language)

    def analyze_commit(self, repo_name, commit):
        with self.health:
            if len(commit.parents) == 0:
                self.analyze_initial_commit(repo_name, commit)
            elif len(commit.parents) == 1:
                self.analyze_regular_commit(repo_name, commit)
            else:
                LOGGER.debug('Skipping merge commit')

    def analyze_regular_commit(self, repo_name, commit):
        for diff in commit.parents[0].diff(commit):
            if diff.new_file:
                self.get_parser(diff.b_path).analyze_blob(repo_name, commit, diff.b_path)
            elif diff.deleted_file:
                self.get_parser(diff.a_path).analyze_blob(repo_name, commit.parents[0], diff.a_path)
            else:
                self.get_parser(diff.b_path).analyze_diff(repo_name, commit, diff)

    def analyze_initial_commit(self, repo_name, commit):
        for blob in commit.tree.traverse(predicate = lambda item, depth: item.type == 'blob'):
            self.get_parser(blob.path).analyze_blob(repo_name, commit, blob.path)

    def close(self):
        for parser in self.parsers.values():
            parser.close()
