import abc
import json

class LanguageParser(metaclass = abc.ABCMeta):

    DUMMY_CALLBACK = lambda language, module, submodule, date, count: raise NotImplementedError('You should provide your own callback')

    def __init__(self, callback = DUMMY_CALLBACK):
        self.callback = callback

    @abc.abstractmethod
    def get_context(self, tree, path):
        return dict()

    @property
    @abc.abstractmethod
    def parser(self):
        pass

    @abc.abstractmethod
    def get_module_counts(self, tree, path):
        if not tree or not path:
            return None
        context = self.get_context(tree, path)
        use_count = self.parser.send(json.dumps({ 'code': base64.b64encode(code).decode('utf-8'), 'context': context }))['use_count']
        return { name: count for name, count in use_count.items() if self.check_relevance(name) }

    @property
    @abc.abstractmethod
    def relevance_checker(self):
        pass

    @abc.abstractmethod
    def check_relevance(self, module):
        return int(self.relevance_checker.send(json.dumps({ 'module': module }))['impact']) > 0

    def analyze_code(self, tree_before, tree_after, path_before, path_after, authored_at):
        module_counts_before = Counter(self.get_module_counts(tree_before, path_before))
        module_counts_after = Counter(self.get_module_counts(tree_after, path_after))
        for module, differential_count in module_counts_after.subtract(module_counts_before).most_common():
            if not differential_count:
                continue
            self.callback(self.name, module.split('.'), authored_at, abs(differential_count))
