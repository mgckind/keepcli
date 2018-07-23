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

try:
    with open('requirements.txt') as f:
        required = f.read().splitlines()
except:
    required = []

try:
    pkgs = find_packages()
except NameError:
    pkgs = ['keepcli']

try:
    import pypandoc
    long_description = pypandoc.convert('README.md', 'rst')
except(IOError, ImportError):
    long_description = open('README.md').read()

setup(
    name='keepcli',
    version=__version__,
    author='Matias Carrasco Kind',
    author_email='mgckind@gmail.com',
    scripts=['bin/keepcli'],
    packages=pkgs,
    license='LICENSE.txt',
    description='Simple unofficial Google Keep Interactive Command Line Interpreter',
    long_description=long_description,
    url='https://github.com/mgckind/keepcli',
    install_requires=required,
)
