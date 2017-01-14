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
            self.unrecognized.update([exc_value.extension])
            LOGGER.debug('Skipping parsing. %s', exc_value)
            return True
        elif exc_type is exceptions.MissingLanguageSupport:
            self.unsupported.update([exc_value.language])
            LOGGER.debug('Skipping parsing. %s', exc_value)
            return True
        elif exc_type is exceptions.UnparsableCode:
            self.unparsable.update([exc_value.language])
            LOGGER.debug('Skipping unparsable code: %s', exc_value)
            return True
        self.attempted += 1

    def as_dict(self):
        unparsable = sum(self.unparsable.values())
        unrecognized = sum(self.unrecognized.values())
        unsupported = sum(self.unsupported.values())
        return { 'unparsable': unparsable, 'unrecognized': unrecognized, 'unsupported': unsupported, 'attempted': self.attempted }

    def __repr__(self):
        fields = self.as_dict()
        return '{}(unparsable={}, unrecognized={}, unsupported={}, attempted={})'.format(
                self.__class__.__name__,
                fields['unparsable'],
                fields['unrecognized'],
                fields['unsupported'],
                fields['attempted'])

if __name__ == '__main__':
    p = ParserHealth()
    print(p)
