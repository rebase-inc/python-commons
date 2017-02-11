from setuptools import setup, find_packages
from shutil import rmtree


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
        install_requires=requirements,
        packages=find_packages(include=(package,))
    )
    previous_pkg = package


