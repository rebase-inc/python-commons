from setuptools import setup
from setuptools.dist import Distribution

class BinaryDistribution(Distribution):
  def is_pure(self):
    return False

with open('./requirements.txt') as reqs:
  REQUIREMENTS = [ req for req in reqs ]

setup(name='tcp', version='0.0.1', distclass = BinaryDistribution, install_requires = REQUIREMENTS)
