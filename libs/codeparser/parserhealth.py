import logging
from collections import Counter

from . import exceptions

LOGGER = logging.getLogger()

class ParserHealth(object):
    def __init__(self):
        self.analyzed = 0
        self.unparsable = Counter()
        self.unrecognized = Counter()
        self.unsupported = Counter()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is exceptions.UnrecognizedExtension:
            self.unrecognized[exc_value.extension] += 1
            LOGGER.debug('Skipping parsing. {}'.format(exc_value))
            return True
        elif exc_type is exceptions.MissingLanguageSupport:
            self.unsupported[exc_value.language] += 1
            LOGGER.debug('Skipping parsing. {}'.format(exc_value))
            return True
        elif exc_type is exceptions.UnparsableCode:
            self.unparsable[exc_value.language] += 1
            LOGGER.debug('Skipping parsing. {}'.format(exc_value))
            return True
        elif exc_type is None:
            self.analyzed += 1
