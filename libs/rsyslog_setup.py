from os import getcwd
from os.path import join
from setuptools import setup, find_packages


pkg = __file__.split('_setup.py')[0]


with open(join(getcwd(), pkg+'_requirements.txt')) as reqs:
    REQUIREMENTS = [ req for req in reqs ]


setup(
    name=pkg, 
    version='0.0.1',
    install_requires=REQUIREMENTS,
    packages=find_packages(include=(pkg,))
)


