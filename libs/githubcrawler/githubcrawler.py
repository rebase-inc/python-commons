import os
import git
import time
import shutil
import logging
from datetime import datetime

from github import Github, GithubObject, GithubException, RateLimitExceededException
from github.Requester import Requester
from github.MainClass import DEFAULT_BASE_URL, DEFAULT_TIMEOUT, DEFAULT_PER_PAGE

LOGGER = logging.getLogger()
logging.getLogger('github').setLevel(logging.WARNING)
logging.getLogger('git').setLevel(logging.WARNING)


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
                    LOGGER.info('Skipping repository "{}"'.format(repo.full_name))
                else:
                    repos_to_crawl.append(repo)
            except GithubException as e:
                LOGGER.exception('Unknown exception for user "{}" and repository "{}": {}'.format(user, repo, e))
        for repo in repos_to_crawl:
            start = time.time()
            self.crawl_repo(user, repo)
            LOGGER.info('Crawling repo {} for user {} took {} seconds'.format(repo.full_name, user.login, time.time() - start))

    def crawl_repo(self, user, repo):
        all_commits = repo.get_commits(author = user.login)
        if not next(all_commits.__iter__(), None): # totalCount doesn't work
            return
        else:
            cloned_repo = self.clone(repo)
            for commit in repo.get_commits(author = user.login):
                self.analyze_commit(cloned_repo.commit(commit.sha))
            if os.path.isdir(cloned_repo.working_dir):
                shutil.rmtree(cloned_repo.working_dir)

    def clone(self, repo):
        url = repo.clone_url.replace('https://github.com', self.oauth_clone_prefix, 1)
        clone_base_dir = self.small_repo_dir if repo.size <= self.repo_cutoff_in_bytes else self.large_repo_dir
        repo_path = os.path.join(clone_base_dir, repo.name)
        if os.path.isdir(repo_path):
            shutil.rmtree(repo_path)
        try:
            LOGGER.debug('Cloning repo "{}" to {}'.format(repo.full_name, 'memory' if clone_base_dir == self.small_repo_dir else 'file'))
            return git.Repo.clone_from(url, repo_path)
        except git.exc.GitCommandError as e:
            if clone_base_dir == self.small_repo_dir:
                LOGGER.error('Failed to clone {} repository into memory ({}), trying to clone to disk...'.format(repo.name, e))
                repo_path = os.path.join(self.large_repo_dir, repo.name)
                return git.Repo.clone_from(url, repo_path)
            else:
                raise e

    def analyze_commit(self, commit):
        if len(commit.parents) == 0:
            return self.analyze_initial_commit(commit)
        elif len(commit.parents) == 1:
            return self.analyze_regular_commit(commit)
        else:
            return self.analyze_merge_commit(commit)

    def analyze_regular_commit(self, commit):
        for diff in commit.parents[0].diff(commit, create_patch = True):
            tree_before = commit.parents[0].tree if not diff.new_file else None
            tree_after = commit.tree[diff.b_path].data_stream.read() if not diff.deleted_file else None
            path_before = diff.a_path
            path_after = diff.b_path
            self.callback(tree_before, tree_after, path_before, path_after, commit.authored_datetime)

    def analyze_initial_commit(self, commit):
        for blob in commit.tree.traverse(predicate = lambda item, depth: item.type == 'blob'):
            tree_before = None
            tree_after = commit.tree
            path_before = None
            path_after = blob.path
            self.callback(tree_before, tree_after, path_before, path_after, commit.authored_datetime)

    def analyze_merge_commit(self, commit):
        LOGGER.debug('Skipping merge commit')


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

