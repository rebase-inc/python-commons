import abc

class Population(metaclass = abc.ABCMeta):

    @abc.abstractmethod
    def user_ranking_exists(self, username, version = None):
        pass

    @abc.abstractmethod
    def calculate_rankings(self, knowledge, *name):
        pass

    @abc.abstractmethod
    def add_user_knowledge(self, username, knowledge):
        pass

    @abc.abstractmethod
    def add_user_ranking(self, username, ranking):
        pass

    @abc.abstractmethod
    def get_user_knowledge(self, username):
        pass
