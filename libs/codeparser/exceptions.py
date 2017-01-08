class ParserError(Exception):
    pass

class UnrecognizedExtension(ParserError):
    def __init__(self, extension):
        super().__init__()
        self.extension = extension

    def __str__(self):
        return 'Unrecognized extension: {}'.format(self.extension)

class MissingLanguageSupport(ParserError):
    def __init__(self, language):
        super().__init__()
        self.language = language

    def __str__(self):
        return 'Unsupported language: {}'.format(self.language)

class UnparsableCode(ParserError):
    def __init__(self, language):
        super().__init__()
        self.language = language

    def __str__(self):
        return 'Unparsable code in {}'.format(self.language)