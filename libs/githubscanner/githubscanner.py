import signal
import logging

from codeparser import CodeParser
from githubcrawler import GithubCommitCrawler
from knowledgemodel import Knowledge, S3Population, PostgresPopulation

from . import MeasuredJobProgress

LOGGER = logging.getLogger()

class GithubCodeScanner(object):

    def __init__(self, token, s3bucket, clone_config = None, s3config = None, github_id = None, timeout = 360, knowledge_depth = 2):
        self.timeout      = timeout
        self.crawler      = GithubCommitCrawler(token, clone_config, github_id, keepalive = self._rq_keepalive)
        self.github_id    = github_id or self.crawler.authorized_login
        self.knowledge    = Knowledge()
        self.s3population = S3Population(s3bucket, s3config, depth = knowledge_depth)
        self.parser       = CodeParser(callback = self.knowledge.add_reference)
        self.progress     = MeasuredJobProgress()

    def skip(self, repo, log = True):
        skip = not self.parser.supports_any_of(*repo.get_languages().keys())
        if skip and log:
            LOGGER.debug('Skipping repo {} because of missing language support'.format(repo.full_name))
        return skip

    def callback(self, repo_name, commit):
        self.parser.analyze_commit(repo_name, commit)
        self.progress.mark_finished(repo_name)
        self._rq_keepalive()

    def add_step(self, name, *args):
        self.progress.add_step(name)
        self._rq_keepalive()

    def _rq_keepalive(self, *args, **kwargs):
        # has extra arguments so that we can pass it around more easily
        # this takes less than one microsecond per call, so it's okay that we call it very often
        signal.alarm(self.timeout)

    def scan_all(self, force_overwrite = False):
        if self.s3population.user_knowledge_exists(self.github_id, self.knowledge.version) and not force_overwrite:
            LOGGER.info('User "{}" scan is up to date. Skipping scan'.format(self.github_id))
            return
        else:
            LOGGER.debug('Initializing progress...')
            self.crawler.crawl_repos(self.add_step, lambda repo: self.skip(repo, False), remote_only = True)
            LOGGER.debug('Starting scan...')
            self.crawler.crawl_repos(self.callback, self.skip)
            self.s3population.add_user_knowledge(self.github_id, self.knowledge)

    def scan_repo(self, name, cleanup = True):
        self.crawler.crawl_individual_repo(name, self.add_step, remote_only = True)
        self.crawler.crawl_individual_repo(name, self.callback, cleanup = cleanup)

    def scan_commit(self, repo_name, commit_sha, cleanup = True):
        self.crawler.crawl_individual_commit(repo_name, commit_sha, self.add_step, remote_only=True)
        self.crawler.crawl_individual_commit(repo_name, commit_sha, self.callback, cleanup = cleanup)

