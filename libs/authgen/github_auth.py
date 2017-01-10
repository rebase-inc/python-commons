import datetime
from github import Github

def create_access_token(username, password, note):
    github_user = Github(username, password).get_user()
    for auth in github_user.get_authorizations():
        if auth.note == note:
            auth.delete()
    return github_user.create_authorization(scopes = ['public_repo'], note = note).token

def delete_access_token(username, password, token):
    github_user = Github(username, password).get_user()
    for auth in github_user.get_authorizations():
        if auth.token == token:
            auth.delete()

if __name__ == '__main__':
    import os
    username = os.environ['GITHUB_CRAWLER_USERNAME']
    password = os.environ['GITHUB_CRAWLER_PASSWORD']
    token_note = 'mock token' 
    token = create_access_token(username, password, token_note)
    print(token)
    delete_access_token(username, password, token)
