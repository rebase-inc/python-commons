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
    name='authgen', 
    version='0.0.2',
    py_modules=['__init__', 'github_auth'],
    install_requires = REQUIREMENTS
    )
