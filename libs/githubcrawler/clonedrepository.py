import os
import shutil
import logging

import git

LOGGER = logging.getLogger()
logging.getLogger('git').setLevel(logging.WARNING)

class ClonedRepository(object):

    def __init__(self, remote, token, config, keepalive, cleanup = True):
        prefix = 'https://{token}@github.com'.format(token = token)
        url = remote.clone_url.replace('https://github.com', prefix, 1)
        in_memory = remote.size <= config['tmpfs_cutoff']
        self.cleanup = cleanup
        try:
            self.path = os.path.join(config['tmpfs_drive'] if in_memory else config['fs_drive'], remote.name)
            LOGGER.debug('Cloning repo "{}" {}'.format(remote.full_name, 'in memory' if in_memory else 'to filesystem'))
            self.repo = git.Repo.clone_from(url, self.path, progress = keepalive)
        except git.exc.GitCommandError as exc:
            if hasattr(self, 'repo'):
                del self.repo
            shutil.rmtree(self.path, ignore_errors = True)
            if in_memory:
                LOGGER.error('Failed to clone repo "{}" to memory, trying to clone to filesystem'.format(remote.full_name))
                self.path = os.path.join(config['fs_drive'], remote.name)
                self.repo = git.Repo.clone_from(url, self.path, progress = keepalive)
            else:
                raise exc

    def __enter__(self):
        return self.repo

    def __exit__(self, exc_type, exc_value, traceback):
        #del self.repo # prevents git command processes from hanging around
        self.repo.git.clear_cache()
        if self.cleanup:
            shutil.rmtree(self.path, ignore_errors = True)
