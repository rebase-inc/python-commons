import os
import git
import time
import shutil
import logging
from typing import Callable, Any
from datetime import datetime
from functools import lru_cache
from itertools import filterfalse
from collections import Counter

from github import Github, GithubObject, GithubException, RateLimitExceededException
from github.Requester import Requester
from github.MainClass import DEFAULT_BASE_URL, DEFAULT_TIMEOUT, DEFAULT_PER_PAGE

LOGGER = logging.getLogger()
logging.getLogger('github').setLevel(logging.WARNING)
logging.getLogger('git').setLevel(logging.WARNING)

DEFAULT_CONFIG = {
        'tmpfs_dir': '/repos',
        'fs_dir': '/bigrepos',
        'tmpfs_cutoff': 262144000 # 250M
        }

class ClonedRepository(object):

    def __init__(self, remote, token, config = DEFAULT_CONFIG):
        prefix = 'https://{token}@github.com'.format(token = token)
        url = remote.clone_url.replace('https://github.com', prefix, 1)
        in_memory = remote.size <= config['tmpfs_cutoff']
        try:
            self.path = os.path.join(config['tmpfs_dir'] if in_memory else config['fs_dir'], remote.name)
            LOGGER.debug('Trying to clone repo "{}" {}'.format(remote.full_name, 'in memory' if in_memory else 'to filesystem'))
            self.repo = git.Repo.clone_from(url, self.path)
        except git.exc.GitCommandError as exc:
            shutil.rmtree(self.path)
            if in_memory:
                LOGGER.error('Failed to clone repo "{}" to memory, trying to clone to filesystem'.format(remote.full_name))
                self.path = os.path.join(config['fs_dir'], repo.name)
            else:
                raise exc

    def __enter__(self):
        return self.repo

    def __exit__(self, exc_type, exc_value, traceback):
        shutil.rmtree(self.path, ignore_errors = True)

class GithubCommitCrawler(object):

    def __init__(self, access_token, clone_config = DEFAULT_CONFIG):
        self.access_token = access_token
        self.clone_config = {**DEFAULT_CONFIG, **clone_config}
        self.api = RateLimitAwareGithubAPI(login_or_token = access_token)

    def crawl_public_repos(self, username, callback, skip = lambda repo: false, remote_only = False):
        user = self.api.get_user(login = username)
        self._crawl_user_repos(user, callback, skip, remote_only)

    def crawl_authorized_repos(self, callback, skip = lambda repo: False, remote_only = False):
        user = self.api.get_user()
        self._crawl_user_repos(user, callback, skip, remote_only)

    def _crawl_user_repos(self, user, callback, skip, remote_only):
        for repo in filterfalse(skip, user.get_repos(**{'type': 'all'})):
            if remote_only:
                for commit in repo.get_commits(author = user.login):
                    callback(repo.full_name, commit)
            else:
                with ClonedRepository(repo, self.access_token, self.clone_config) as local_repo:
                    for commit in repo.get_commits(author = user.login):
                        callback(repo.full_name, local_repo.commit(commit.sha))

class RateLimitAwareGithubAPI(Github):

    def __init__(self, login_or_token=None, password=None, base_url=DEFAULT_BASE_URL,
            timeout=DEFAULT_TIMEOUT, client_id=None, client_secret=None, user_agent='PyGithub/Python',
            per_page=DEFAULT_PER_PAGE, api_preview=False):
        super().__init__(login_or_token=login_or_token, password=password, base_url=base_url,
            timeout=timeout, client_id=client_id, client_secret=client_secret, user_agent=user_agent,
            per_page=per_page, api_preview=api_preview)
        self._Github__requester = RateLimitAwareRequester(login_or_token=login_or_token, password=password, base_url=base_url,
            timeout=timeout, client_id=client_id, client_secret=client_secret, user_agent=user_agent,
            per_page=per_page, api_preview=api_preview)

class HashableDict(dict):
    def __hash__(self):
        return hash(tuple(sorted(self.items())))

class RateLimitAwareRequester(Requester):

    def __init__(self, max_retries = 3, *args, **kwargs):
        kwargs['per_page'] = 100
        super().__init__(*args, **kwargs)
        self.consecutive_failed_attempts = 0
        self.max_retries = max_retries
        self.wait_until = None

    @lru_cache()
    def __requestEncode(self, cnx, verb, url, parameters, requestHeaders, input, encode):
        if self.consecutive_failed_attempts >= self.max_retries:
            raise GithubRateLimitMaxRetries(cnx, verb, url)

        if self.wait_until:
            LOGGER.debug('Sleeping for {:.2f} seconds'.format((self.wait_until - datetime.now()).total_seconds()))
            time.sleep((self.wait_until - datetime.now()).total_seconds())
            self.wait_until = None

        try:
            response = super()._Requester__requestEncode(cnx, verb, url, parameters, requestHeaders, input, encode)
            self.consecutive_failed_attempts = 0
            return response
        except ConnectionResetError as exc:
            LOGGER.exception('Connection reset!')
            self.consecutive_failed_attempts += 1
            return self._Requester__requestEncode(cnx, verb, url, parameters, requestHeaders, input, encode)
        except RateLimitExceededException:
            LOGGER.info('Rate limited from GitHub API!')
            self.wait_until = datetime.utcfromtimestamp(self.rate_limiting_resettime)
            self.consecutive_failed_attempts += 1
            return self._Requester__requestEncode(cnx, verb, url, parameters, requestHeaders, input, encode)

    def _Requester__requestEncode(self, cnx, verb, url, parameters, requestHeaders, input, encode):
        parameters = HashableDict(parameters) if isinstance(parameters, dict) else parameters
        return self.__requestEncode(cnx, verb, url, parameters, requestHeaders, input, encode)
