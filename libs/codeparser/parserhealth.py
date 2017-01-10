import logging
from collections import Counter

from . import exceptions

LOGGER = logging.getLogger()

class ParserHealth(object):
    def __init__(self):
        self.attempted = 0
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
        self.attempted += 1

    def __repr__(self):
        unparsable = sum(self.unparsable.values())
        unrecognized = sum(self.unrecognized.values())
        unsupported = sum(self.unsupported.values())
        return '{}(unparsable={}, unrecognized={}, unsupported={}, attempted={})'.format(self.__class__.__name__, unparsable, unrecognized, unsupported, self.attempted)

if __name__ == '__main__':
    p = ParserHealth()
    print(p)
