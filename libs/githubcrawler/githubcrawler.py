import os
import git
import time
import shutil
import logging
from datetime import datetime
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

def _report_progress(commits_scanned, all_commits):
    LOGGER.info('{:.1%}'.format(sum(commits_scanned.values()) / float(len(all_commits.values()))))

class GithubCommitCrawler(object):

    def __init__(self, callback, access_token, config, report_progress = _report_progress, username = None):
        self._username = username
        self.config = {**DEFAULT_CONFIG, **config}
        self.api = RateLimitAwareGithubAPI(login_or_token = access_token)
        self.oauth_clone_prefix = 'https://{access_token}@github.com'.format(access_token = access_token)
        self.callback = callback
        self.tmpfs_dir = self.config['tmpfs_dir']
        self.fs_dir = self.config['fs_dir']
        self.tmpfs_cutoff = self.config['tmpfs_cutoff']
        self.report_progress = report_progress

    @property
    def user(self):
        if not hasattr(self, '_user'):
            self._user = self.api.get_user(self._username or GithubObject.NotSet) # if user is owner of auth token, we can't set user here *facepalm*
        return self._user

    def initialize_progress(self, skip):
        # TODO: Cache these requests, since we do them twice
        repos_to_crawl = Counter()
        for repo in self.user.get_repos():
            if not skip(repo):
                commit_count = 0
                for commit in repo.get_commits(author = self.user.login):
                    commit_count += 1
                repos_to_crawl[repo.full_name] = commit_count
        self.progress = (Counter(), repos_to_crawl)
        self.report_progress(*self.progress)

    def update_progress(self, repo, commits = 1):
        self.progress[0][repo.full_name] += commits
        self.report_progress(*self.progress)

    def crawl_all_repos(self, skip = lambda repo: False):
        LOGGER.info('Crawling all repositories for github user {}'.format(self.user.login))
        self.initialize_progress(skip)
        for repo in self.user.get_repos():
            if skip(repo):
                LOGGER.info('Skipping crawling repo "{}"'.format(repo.full_name))
            start = time.time()
            self.crawl_repo(repo)
            LOGGER.debug('Crawling repo {} for user {} took {} seconds'.format(repo.full_name, self.user.login, time.time() - start))

    def crawl_repo(self, repo):
        all_commits = repo.get_commits(author = self.user.login)
        if not next(all_commits.__iter__(), None): # totalCount doesn't work
            return
        else:
            cloned_repo = self.clone(repo, repo.size <= self.tmpfs_cutoff)
            for commit in repo.get_commits(author = self.user.login):
                self.analyze_commit(repo, cloned_repo.commit(commit.sha))
            if os.path.isdir(cloned_repo.working_dir):
                shutil.rmtree(cloned_repo.working_dir)

    def clone(self, repo, in_memory = True):
        url = repo.clone_url.replace('https://github.com', self.oauth_clone_prefix, 1)
        clone_path = os.path.join(self.tmpfs_dir if in_memory else self.fs_dir, repo.name)
        shutil.rmtree(clone_path, ignore_errors = True)
        LOGGER.debug('Cloning repo "{}" {}'.format(repo.full_name, 'in memory' if in_memory else 'to filesystem'))
        try:
            return git.Repo.clone_from(url, clone_path)
        except git.exc.GitCommandError as exc:
            shutil.rmtree(clone_path, ignore_errors = True)
            if in_memory:
                LOGGER.error('Failed to clone {} repository into memory, trying to clone to disk'.format(repo.name))
                return self.clone(repo, in_memory = False)
            else:
                raise exc

    def analyze_commit(self, repo, commit):
        if len(commit.parents) == 0:
            return self.analyze_initial_commit(repo, commit)
        elif len(commit.parents) == 1:
            return self.analyze_regular_commit(repo, commit)
        else:
            return self.analyze_merge_commit(repo, commit)
        self.update_progress(repo)

    def analyze_regular_commit(self, repo, commit):
        for diff in commit.parents[0].diff(commit, create_patch = True):
            tree_before = commit.parents[0].tree if not diff.new_file else None
            tree_after = commit.tree if not diff.deleted_file else None
            path_before = diff.a_path
            path_after = diff.b_path
            self.callback(repo, commit, tree_before, tree_after, path_before, path_after, commit.authored_datetime)

    def analyze_initial_commit(self, repo, commit):
        for blob in commit.tree.traverse(predicate = lambda item, depth: item.type == 'blob'):
            tree_before = None
            tree_after = commit.tree
            path_before = None
            path_after = blob.path
            self.callback(repo, commit, tree_before, tree_after, path_before, path_after, commit.authored_datetime)

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

    def __init__(self, max_retries = 3, *args, **kwargs):
        kwargs['per_page'] = 100
        super().__init__(*args, **kwargs)
        self.consecutive_failed_attempts = 0
        self.max_retries = max_retries
        self.wait_until = None

    def _Requester__requestEncode(self, *args, **kwargs):
        if self.consecutive_failed_attempts >= self.max_retries:
            raise GithubRateLimitMaxRetries(*args[0:3])

        if self.wait_until:
            LOGGER.debug('Sleeping for {:.2f} seconds'.format((self.wait_until - datetime.now()).total_seconds()))
            time.sleep((self.wait_until - datetime.now()).total_seconds())
            self.wait_until = None

        try:
            response = super()._Requester__requestEncode(*args, **kwargs)
            self.consecutive_failed_attempts = 0
            return response
        except ConnectionResetError as exc:
            LOGGER.exception('Connection reset!')
            self.consecutive_failed_attempts += 1
            return self._Requester__requestEncode(*args, **kwargs)
        except RateLimitExceededException:
            LOGGER.info('Rate limited from GitHub API!')
            self.wait_until = datetime.utcfromtimestamp(self.rate_limiting_resettime)
            self.consecutive_failed_attempts += 1
            return self._Requester__requestEncode(*args, **kwargs)

