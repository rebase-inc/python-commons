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
    name='knowledgemodel', 
    version='0.0.1',
    packages=['knowledgemodel'],
    package_dir = {'knowledgemodel': 'src'},
    install_requires = REQUIREMENTS
    )
