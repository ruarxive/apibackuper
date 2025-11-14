# This is purely the result of trial and error.

import sys
import io
import codecs
import re
import os

from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand

open_as_utf = lambda x: io.open(x, encoding='utf-8')

# Read version and metadata from __init__.py without importing
def get_version_and_metadata():
    """Read version and metadata from apibackuper/__init__.py"""
    init_path = os.path.join(os.path.dirname(__file__), 'apibackuper', '__init__.py')
    with open(init_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    version_match = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", content)
    author_match = re.search(r"__author__\s*=\s*['\"]([^'\"]+)['\"]", content)
    licence_match = re.search(r"__licence__\s*=\s*['\"]([^'\"]+)['\"]", content)
    doc_match = re.search(r'"""(.*?)"""', content, re.DOTALL)
    
    version = version_match.group(1) if version_match else '0.0.0'
    author = author_match.group(1) if author_match else 'Unknown'
    licence = licence_match.group(1) if licence_match else 'MIT'
    doc = doc_match.group(1).strip() if doc_match else 'apibackuper'
    
    return version, author, licence, doc

__version__, __author__, __licence__, __doc__ = get_version_and_metadata()

class PyTest(TestCommand):
    # `$ python setup.py test' simply installs minimal requirements
    # and runs the tests with no fancy stuff like parallel execution.
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = [
            '--doctest-modules', '--verbose',
            './apibackuper', './tests'
        ]
        self.test_suite = True

    def run_tests(self):
        import pytest
        sys.exit(pytest.main(self.test_args))


tests_require = [
    # Pytest needs to come last.
    # https://bitbucket.org/pypa/setuptools/issue/196/
    'pytest',
    'mock',
]


install_requires = [
    'typer', 'lxml', 'urllib3', 'requests', 'xmltodict', 'PyYAML', 'jsonschema>=4.0.0', 'tqdm>=4.66.0'
]


# Conditional dependencies:

# sdist
if 'bdist_wheel' not in sys.argv:
    try:
        # noinspection PyUnresolvedReferences
        import argparse
    except ImportError:
        install_requires.append('argparse>=1.2.1')


# bdist_wheel
extras_require = {
    # https://wheel.readthedocs.io/en/latest/#defining-conditional-dependencies
#    'python_version == "3.0" or python_version == "3.1"': ['argparse>=1.2.1'],
}



def long_description():
    with codecs.open('README.md', encoding='utf8') as f:
        return f.read()


setup(
    name='apibackuper',
    version=__version__,
    description=__doc__.strip(),
    long_description=long_description(),
    long_description_content_type='text/markdown',
    url='https://github.com/datacoon/apibackuper/',
    download_url='https://github.com/datacoon/apibackuper/',
    packages=find_packages(exclude=('tests', 'tests.*')),
    include_package_data=True,
    author=__author__,
    author_email='ivan@begtin.tech',
    license=__licence__,
    entry_points={
        'console_scripts': [
            'apibackuper = apibackuper.__main__:main',
        ],
    },
    extras_require=extras_require,
    install_requires=install_requires,
    tests_require=tests_require,
    cmdclass={'test': PyTest},
    zip_safe=False,
    keywords='api json jsonl csv bson cli dataset',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: BSD License',
        'Topic :: Software Development',
        'Topic :: System :: Networking',
        'Topic :: Terminals',
        'Topic :: Text Processing',
        'Topic :: Utilities'
    ],
)
