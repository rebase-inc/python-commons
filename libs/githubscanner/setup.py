import os 
from setuptools import setup
from setuptools.dist import Distribution

class BinaryDistribution(Distribution):
  def is_pure(self):
    return False

WORKING_DIR = os.path.dirname(os.path.realpath(__file__))
with open(os.path.join(WORKING_DIR, 'requirements.txt')) as reqs:
  REQUIREMENTS = [ req for req in reqs ]

setup(
    name='githubscanner', 
    version='0.0.1',
    py_modules=['githubscanner'],
    install_requires = REQUIREMENTS
    )
