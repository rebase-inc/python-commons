import os
import time
import git
import shutil
import logging
from datetime import datetime

from github import Github, GithubObject, GithubException, RateLimitExceededException
from github.Requester import Requester
from github.MainClass import DEFAULT_BASE_URL, DEFAULT_TIMEOUT, DEFAULT_PER_PAGE

LOGGER = logging.getLogger()

class GithubCommitCrawler(object):
    def __init__(self, access_token, callback, small_repo_dir, large_repo_dir, repo_cutoff_in_bytes):
        self.api = RateLimitAwareGithubAPI(login_or_token = access_token)
        self.oauth_clone_prefix = 'https://{access_token}@github.com'.format(access_token = access_token)
        self.callback = callback
        self.small_repo_dir = small_repo_dir
        self.large_repo_dir = large_repo_dir
        self.repo_cutoff_in_bytes = repo_cutoff_in_bytes


    def crawl_all_repos(self, skip = lambda repo: False, user = None):
        user = self.api.get_user(user or GithubObject.NotSet) # if user is owner of auth token, we can't set user here *facepalm*
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
            self.crawl_repo(user, repo)

    def crawl_repo(self, user, repo):
        all_commits = repo.get_commits(author = user.login)
        if not next(all_commits.__iter__(), None): # totalCount doesn't work
            LOGGER.debug('Skipping {} repo (no commits found for user {})'.format(repo.name, user.login))
        else:
            cloned_repo = self.clone(repo)
            for commit in repo.get_commits(author = user.login):
                self.callback(cloned_repo.commit(commit.sha))
            if os.path.isdir(cloned_repo.working_dir):
                shutil.rmtree(cloned_repo.working_dir)

    def clone(self, repo):
        url = repo.clone_url.replace('https://github.com', self.oauth_clone_prefix, 1)
        clone_base_dir = self.small_repo_dir if repo.size <= self.repo_cutoff_in_bytes else self.large_repo_dir
        repo_path = os.path.join(clone_base_dir, repo.name)
        if os.path.isdir(repo_path):
            shutil.rmtree(repo_path)
        try:
            return git.Repo.clone_from(url, repo_path)
        except git.exc.GitCommandError as e:
            if clone_base_dir == self.small_repo_dir:
                LOGGER.exception('Failed to clone {} repository into memory ({}), trying to clone to disk...'.format(repo.name, e))
                repo_path = os.path.join(self.large_repo_dir, repo.name)
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
        kwargs['per_page'] = 100
        super().__init__(*args, **kwargs)
        self.consecutive_failed_attempts = 0
        self.max_retries = max_retries
        self.min_delay = min_delay
        self.last_request_time = None
        self.wait_until = None

    def _Requester__requestEncode(self, *args, **kwargs):
        seconds_since_last_request = (datetime.now() - (self.last_request_time or datetime.min)).total_seconds()
        if self.consecutive_failed_attempts >= self.max_retries:
            raise GithubRateLimitMaxRetries(*args[0:3])
        elif self.wait_until:
            LOGGER.debug('Sleeping for {:.2f} seconds'.format((self.wait_until - datetime.now()).total_seconds()))
            time.sleep((self.wait_until - datetime.now()).total_seconds())
            self.wait_until = None
        elif seconds_since_last_request < self.min_delay:
            LOGGER.debug('Minimum request delay of {} seconds not reached - sleeping for {:.2f} seconds'.format(self.min_delay, self.min_delay - seconds_since_last_request))
            time.sleep(self.min_delay - seconds_since_last_request)

        try:
            self.last_request_time = datetime.utcnow()
            return super()._Requester__requestEncode(*args, **kwargs)
        except ConnectionResetError as exc:
            LOGGER.exception('Connection reset!')
            self.consecutive_failed_attempts += 1
            return self._Requester__requestEncode(*args, **kwargs)
        except RateLimitExceededException:
            LOGGER.info('Rate limited from GitHub API!')
            self.wait_until = datetime.utcfromtimestamp(self.rate_limiting_resettime)
            self.consecutive_failed_attempts += 1
            return self._Requester__requestEncode(*args, **kwargs)

