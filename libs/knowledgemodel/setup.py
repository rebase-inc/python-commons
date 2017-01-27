import os 
from setuptools import setup
from setuptools.dist import Distribution


WORKING_DIR = os.path.dirname(os.path.realpath(__file__))
with open(os.path.join(WORKING_DIR, 'requirements.txt')) as reqs:
  REQUIREMENTS = [ req for req in reqs ]

setup(
    name='knowledgemodel', 
    version='0.0.1',
    py_modules=[
        '__init__',
        'knowledgemodel',
        'populationmodel',
        's3population',
        'postgrespopulation',
        'rankingmodel'
    ],
    install_requires = REQUIREMENTS
    )
