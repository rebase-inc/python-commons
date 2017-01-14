import os 
from setuptools import setup
from setuptools.dist import Distribution


WORKING_DIR = os.path.dirname(os.path.realpath(__file__))
with open(os.path.join(WORKING_DIR, 'requirements.txt')) as reqs:
  REQUIREMENTS = [ req for req in reqs ]

setup(
    name='codeparser', 
    version='0.0.2',
    py_modules=[
        '__init__',
        'codeparser',
        'exceptions',
        'javascriptparser',
        'languageparser',
        'parserhealth',
        'pythonparser',
    ],
    install_requires = REQUIREMENTS
    )
