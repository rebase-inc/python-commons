from setuptools import setup, find_packages
from shutil import rmtree


all_requirements = {
    'asynctcp': {
        'requires': (
            'curio',
            'rsyslog'
        ),
        'dependency_links': ['https://github.com/dabeaz/curio/tarball/master'],
    },
    'authgen': {
        'requires': ( 'PyGithub', ),
    },
    'codeparser': {
        'requires': ( 'asynctcp', ),
    },
    'githubcrawler': {
        'requires': (
            'PyGithub',
            'gitpython',
            'frozendict',
        ),
    },
    'githubscanner': {
        'requires': (
            'rq',
            'codeparser',
            'githubcrawler',
            'knowledgemodel',
        ),
    },
    'knowledgemodel': {
        'requires': (
            'boto3',
            'gitpython',
            'pip',
            'psycopg2',
            'PyGithub',
            'redis',
            'rq',
            'stdlib-list',
            'asynctcp',
            'rsyslog',
        )
    },
    'rsyslog': {
        'requires':tuple(),
    },
}


previous_pkg = None


for package, requirements in all_requirements.items():
    if previous_pkg:
        rmtree('/tmp/build/lib/'+previous_pkg)
        path = '/tmp/build_bdist/wheel/'+previous_pkg
        rmtree(path)
        dist_info_path = path+'-0.0.1.dist-info'
        rmtree(dist_info_path)
    setup(
        name=package, 
        version='0.0.1',
        install_requires=requirements['requires'],
        packages=find_packages(include=(package,)),
        dependency_links=requirements['dependency_links'] if 'dependency_links' in requirements else [],
    )
    previous_pkg = package


