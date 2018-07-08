import sys
import os
try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup

prjdir = os.path.dirname(__file__)
__version__ = ''


def read(filename):
    return open(os.path.join(prjdir, filename)).read()


exec(open('keepcli/version.py').read())

with open('requirements.txt') as f:
    required = f.read().splitlines()

try:
    pkgs = find_packages()
except NameError:
    pkgs = ['keepcli']
setup(
    name='keepcli',
    version=__version__,
    author='Matias Carrasco Kind',
    author_email='mgckind@gmail.com',
    scripts=['bin/keepcli'],
    packages=pkgs,
    license='LICENSE.txt',
    description='Simple unofficial Google Keep Interactive Command Line Interpreter',
    long_description=read('README.md'),
    url='https://github.com/mgckind/keepcli',
    install_requires=required,
)
