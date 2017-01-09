from github import Github

def create_access_token(username, password, note):
    github_user = Github(username, password).get_user()
    for auth in github_user.get_authorizations():
        if auth.note == token_note:
            auth.delete()
    return github_user.create_authorization(scopes = ['public_repo'], note = token_note).token

if __name__ == '__main__':
    import os
    username = os.environ['GITHUB_CRAWLER_USERNAME']
    password = os.environ['GITHUB_CRAWLER_PASSWORD']
    token_note = 'mock token' 
    print(create_access_token(username, password, token_note))
