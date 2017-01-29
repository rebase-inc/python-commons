from asynctcp import BlockingTcpClient

from . import LanguageParser

PARSER_HOST = 'javascript_parser'
PARSER_PORT = 7777
IMPACT_HOST = 'javascript_impact'
IMPACT_PORT = 9999

class JavascriptParser(LanguageParser):
    language = 'javascript'

    def __init__(self, callback):
        super().__init__(callback)
        self.parsers = []
        self.parsers.append(BlockingTcpClient(PARSER_HOST, PARSER_PORT, timeout = 120))

    def get_context(self, repo_name, commit, path):
        return super().get_context(repo_name, commit, path)

    def check_relevance(self, module):
        return super().check_relevance(module)

    @property
    def relevance_checker(self):
        if not hasattr(self, '_relevance_checker'):
            self._relevance_checker = BlockingTcpClient(IMPACT_HOST, IMPACT_PORT, timeout = 20)
        return self._relevance_checker
