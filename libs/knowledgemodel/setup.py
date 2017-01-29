from os import getcwd
from os.path import basename, dirname, join, realpath
from setuptools import setup, find_packages
from setuptools.dist import Distribution


print('File: {}'.format(__file__))
WORKING_DIR = dirname(realpath(__file__))


with open(join(WORKING_DIR, 'requirements.txt')) as reqs:
    REQUIREMENTS = [ req for req in reqs ]


setup(
    name='knowledgemodel', 
    version='0.0.1',
    install_requires=REQUIREMENTS,
    packages=find_packages(include=(basename(WORKING_DIR),))
)


