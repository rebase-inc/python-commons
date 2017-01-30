from setuptools import setup, find_packages


all_requirements = {
    'asynctcp': ( 'curio==0.4', ),
    'authgen': ( 'PyGithub', ),
    'codeparser': ( 'asynctcp', ),
    'githubcrawler': (
        'PyGithub',
        'gitpython',
        'frozendict',
    ),
    'githubscanner': (
        'rq',
        'codeparser',
        'githubcrawler',
        'knowledgemodel',
    ),
    'knowledgemodel': (
        'gitpython',
        'stdlib-list',
        'pip',
        'PyGithub',
        'python-magic',
        'asynctcp',
        'redis',
        'rq',
        'rsyslog',
    ),
    'rsyslog': tuple(),
}


for package, requirements in all_requirements.items():
    setup(
        name=package, 
        version='0.0.1',
        install_requires=requirements,
        packages=find_packages(include=(package,))
    )


