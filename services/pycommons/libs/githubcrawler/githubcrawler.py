import os
import time
import git
import shutil
import logging
from datetime import datetime

from github import Github, GithubException
from github.Requester import Requester
from github.MainClass import DEFAULT_BASE_URL, DEFAULT_TIMEOUT, DEFAULT_PER_PAGE

LOGGER = logging.getLogger()

CLONE_RAM_DIR = '/repos'
CLONE_FS_DIR = '/big_repos'

class GithubCommitCrawler(object):
    def __init__(self, access_token, callback, clone_ram_dir = CLONE_RAM_DIR, clone_fs_dir = CLONE_FS_DIR):
        self.api = RateLimitAwareGithubAPI(login_or_token = access_token)
        self.oauth_clone_prefix = 'https://{access_token}@github.com'.format(access_token = access_token)
        self.callback = callback
        self.clone_ram_dir = clone_ram_dir
        self.clone_fs_dir = clone_fs_dir

        # TODO: Remove environment variable dependency
        self._in_memory_clone_limit = 1024 * int(os.environ['REPOS_VOLUME_SIZE_IN_MB']) / int(os.environ['CLONE_SIZE_SAFETY_FACTOR'])

    def crawl_all_repos(self, skip = lambda repo: False):
        user = self.api.get_user()
        repos_to_crawl = []
        for repo in user.get_repos():
            try:
                if skip(repo):
                    LOGGER.debug('Skipping repository "{}"'.format(repo.full_name))
                else:
                    repos_to_crawl.append(repo)
            except GithubException as e:
                LOGGER.exception('Unknown exception for user "{}" and repository "{}": {}'.format(user, repo, e))
        for repo in repos_to_crawl:
            self.crawl_repo(repo)

    def crawl_repo(self, repo):
        all_commits = repo.get_commits(author = self.api.get_user().login)
        if not (all_commits or all_commits.totalCount()):
            LOGGER.debug('Skipping {} repo (no commits found for user {})'.format(repo.name, self.user.login))
        else:
            cloned_repo = self.clone(repo)
            for commit in repo.get_commits(author = self.api.get_user().login):
                self.callback(cloned_repo.commit(commit.sha))
        if os.path.isdir(cloned_repo.working_dir):
            shutil.rmtree(cloned_repo.working_dir)

    def clone(self, repo):
        url = repo.clone_url.replace('https://github.com', self.oauth_clone_prefix, 1)
        clone_base_dir = self.clone_ram_dir if repo.size <= self._in_memory_clone_limit else self.clone_fs_dir
        repo_path = os.path.join(clone_base_dir, repo.name)
        if os.path.isdir(repo_path):
            shutil.rmtree(repo_path)
        try:
            return git.Repo.clone_from(url, repo_path)
        except git.exc.GitCommandError as e:
            if clone_base_dir == self.clone_ram_dir:
                LOGGER.exception('Failed to clone {} repository into memory ({}), trying to clone to disk...'.format(repo.name, e))
                repo_path = os.path.join(self.clone_fs_dir, repo.name)
                return git.Repo.clone_from(url, repo_path)
            else:
                raise e

class RateLimitAwareGithubAPI(Github):

    def __init__(self, login_or_token=None, password=None, base_url=DEFAULT_BASE_URL,
            timeout=DEFAULT_TIMEOUT, client_id=None, client_secret=None, user_agent='PyGithub/Python',
            per_page=DEFAULT_PER_PAGE, api_preview=False):
        super().__init__(login_or_token=login_or_token, password=password, base_url=base_url,
            timeout=timeout, client_id=client_id, client_secret=client_secret, user_agent=user_agent,
            per_page=per_page, api_preview=api_preview)
        self._Github__requester = RetryingRequester(login_or_token=login_or_token, password=password, base_url=base_url,
            timeout=timeout, client_id=client_id, client_secret=client_secret, user_agent=user_agent,
            per_page=per_page, api_preview=api_preview)

class RetryingRequester(Requester):
    def __init__(self, max_retries = 3, min_delay = 0.75, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.consecutive_failed_attempts = 0
        self.max_retries = max_retries
        self.min_delay = min_delay
        self.last_request_time = None

        # wait_until is not currently used, but it's there so that, if necessary
        # __requestEncode could be easily extended to pay attention to additional
        # rate limiting headers, such as Retry-After. Additionally, a user of the
        # RetryingRequester or RateLimitAwareGithubAPI could force the requester
        # to wait by setting this variable
        self.wait_until = None

    def _Requester__requestEncode(self, *args, **kwargs):
        seconds_since_last_request = (datetime.now() - (self.last_request_time or datetime.min)).total_seconds()
        if self.consecutive_failed_attempts >= self.max_retries:
            raise GithubRateLimitMaxRetries(*args[0:3])
        elif self.wait_until:
            time.sleep((self.wait_until - datetime.now()).total_seconds())
        elif seconds_since_last_request < self.min_delay:
            LOGGER.debug('Minimum request delay of {} seconds not reached - sleeping for {:.2f} seconds'.format(self.min_delay, self.min_delay - seconds_since_last_request))
            time.sleep(self.min_delay - seconds_since_last_request)

        try:
            self.last_request_time = datetime.utcnow()
            return super()._Requester__requestEncode(*args, **kwargs)
        except GithubException.RateLimitExceededException:
            self.consecutive_failed_attempts += 1
            time_until_reset = (datetime.utcfromtimestamp(self.rate_limiting_resettime) - datetime.utcnow()).total_seconds()
            LOGGER.info('Rate limited from GitHub API! Sleeping for {0:.2f} seconds'.format(time_until_reset))
            time.sleep(time_until_reset)
            return self.__requestEncode(*args, **kwargs)
