import os
import git
import time
import shutil
import socket
import logging
from typing import Callable, Any
from datetime import datetime
from functools import lru_cache
from itertools import filterfalse
from collections import Counter
from http.client import IncompleteRead

from frozendict import frozendict

from github import Github, GithubObject, GithubException, RateLimitExceededException, BadCredentialsException
from github.Requester import Requester
from github.MainClass import DEFAULT_BASE_URL, DEFAULT_TIMEOUT, DEFAULT_PER_PAGE

from . import ClonedRepository

LOGGER = logging.getLogger()
logging.getLogger('github').setLevel(logging.WARNING)

class GithubCommitCrawler(object):

    def __init__(self, access_token, config, login = None, keepalive = None):
        self.access_token = access_token
        self.config = config
        self.api = RateLimitAwareGithubAPI(login_or_token = access_token)
        self.keepalive = keepalive
        self.login = login or GithubObject.NotSet 

    @property
    def authorized_login(self):
        return self.api.get_user().login

    def crawl_repos(self, callback, skip = lambda repo: false, remote_only = False):
        user = self.api.get_user(login = self.login)
        self._crawl_user_repos(user, callback, skip, remote_only, cleanup = True)

    def crawl_individual_repo(self, name, callback, remote_only = False, cleanup = True):
        user = self.api.get_user(login = self.login)
        repo = user.get_repo(name)
        self._crawl_user_repo(user, repo, callback, remote_only, cleanup)

    def crawl_individual_commit(self, repo_name, commit_sha, callback, remote_only = False, cleanup = True):
        repo = self.api.get_user(login = self.login).get_repo(repo_name)
        if remote_only:
            callback(repo.full_name, repo.get_commit(commit_sha))
        else:
            with ClonedRepository(repo, self.access_token, self.config, self.keepalive, cleanup) as local_repo:
                callback(repo.full_name, local_repo.commit(commit_sha))

    def _crawl_user_repos(self, user, callback, skip, remote_only, cleanup):
        repos = filterfalse(skip, filterfalse(lambda r: r.fork, user.get_repos(type = 'all')))
        for repo in self._handle_github_exceptions(repos):
            self._crawl_user_repo(user, repo, callback, remote_only, cleanup)

    def _crawl_user_repo(self, user, repo, callback, remote_only, cleanup):
        all_commits = repo.get_commits(author = user.login)
        if remote_only:
            for commit in all_commits:
                callback(repo.full_name, commit)
        else:
            if not next(all_commits.__iter__(), None): #totalCount doesn't work
                LOGGER.debug('Skipping repo "{}" because user {} has no commits on it'.format(repo.full_name, user.login))
                return
            with ClonedRepository(repo, self.access_token, self.config, self.keepalive, cleanup) as local_repo:
                for commit in all_commits:
                    callback(repo.full_name, local_repo.commit(commit.sha))

    @classmethod
    def _handle_github_exceptions(cls, generator):
        while True:
            try:
                yield next(generator)
            except StopIteration:
                raise
            except GithubException as exc:
                LOGGER.error('Crawling repo failed! {}'.format(str(exc.data)))

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
            LOGGER.error('Connection reset trying to reach {}! Trying again...'.format(url))
            self.consecutive_failed_attempts += 1
            return self.__requestEncode(cnx, verb, url, parameters, requestHeaders, input, encode)
        except ConnectionRefusedError as exc:
            LOGGER.error('Connection refused trying to reach {}! Trying again...'.format(url))
            self.consecutive_failed_attempts += 1
            return self.__requestEncode(cnx, verb, url, parameters, requestHeaders, input, encode)
        except RateLimitExceededException:
            LOGGER.info('Rate limited from GitHub API! Waiting until rate limit reset.')
            self.wait_until = datetime.utcfromtimestamp(self.rate_limiting_resettime)
            self.consecutive_failed_attempts += 1
            return self.__requestEncode(cnx, verb, url, parameters, requestHeaders, input, encode)
        except BadCredentialsException as exc:
            LOGGER.error('Got "Bad Credentials" trying to reach {}! This seems to be a bug in the GitHub API. Trying again...'.format(url))
            return self.__requestEncode(cnx, verb, url, parameters, requestHeaders, input, encode)
        except socket.timeout as exc:
            LOGGER.error('Socket timeout trying to reach {}! This seems to be a bug in the GitHub API. Trying again...'.format(url))
            self.consecutive_failed_attempts += 1
            return self.__requestEncode(cnx, verb, url, parameters, requestHeaders, input, encode)
        except IncompleteRead as exc:
            LOGGER.error('Incomplete read from {}! This seems to be a bug in the GitHub API. Trying again...'.format(url))
            self.consecutive_failed_attempts += 1
            return self.__requestEncode(cnx, verb, url, parameters, requestHeaders, input, encode)

    def _Requester__requestEncode(self, cnx, verb, url, parameters, requestHeaders, input, encode):
        parameters = frozendict(parameters) if isinstance(parameters, dict) else parameters
        return self.__requestEncode(cnx, verb, url, parameters, requestHeaders, input, encode)
