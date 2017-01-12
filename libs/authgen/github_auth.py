import logging
import hashlib
import datetime

from github import Github

LOGGER = logging.getLogger()

def create_access_token(username, password, note):
    github_user = Github(username, password).get_user()
    for auth in github_user.get_authorizations():
        if auth.note == note:
            auth.delete()
    return github_user.create_authorization(scopes = ['public_repo'], note = note).token

def delete_access_token(username, password, token):
    hashed_token = hashlib.sha256(token.encode('utf-8')).hexdigest()
    github_user = Github(username, password).get_user()
    for auth in github_user.get_authorizations():
        if auth.raw_data['hashed_token'] == hashed_token:
            auth.delete()
            break
    else:
        raise Exception('No such token {} found!'.format(token))


if __name__ == '__main__':
    import os
    username = os.environ['GITHUB_CRAWLER_USERNAME']
    password = os.environ['GITHUB_CRAWLER_PASSWORD']
    token_note = 'mock token' 
    token = create_access_token(username, password, token_note)
    print(token)
    delete_access_token(username, password, token)
