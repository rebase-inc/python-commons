class ParserError(Exception):
    pass

class UnrecognizedExtension(ParserError):
    def __init__(self, extension):
        super().__init__()
        self.extension = extension

    def __str__(self):
        if self.extension:
            return 'Unrecognized extension: {}'.format(self.extension)
        else:
            return 'Missing extension'

class MissingLanguageSupport(ParserError):
    def __init__(self, language):
        super().__init__()
        self.language = language

    def __str__(self):
        return 'Unsupported language: {}'.format(self.language)

class UnparsableCode(ParserError):

    def __init__(self, language, url, reason = 'Unknown Reason'):
        super().__init__()
        self.url = url
        self.reason = reason
        self.language = language

    def __str__(self):
        return '{self.url} - ({self.reason})'.format(self = self)
