# This is purely the result of trial and error.

import sys
import io
import codecs
import re

from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand

import apibackuper

open_as_utf = lambda x: io.open(x, encoding='utf-8')

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
    'pymongo', 'click', 'lxml', 'urllib3', 'requests', 'xmltodict'
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



readme = re.sub(r':members:.+|..\sautomodule::.+|:class:|:func:', '', open_as_utf('README.rst').read())
readme = re.sub(r'`Settings`_', '`Settings`', readme)
readme = re.sub(r'`Contributing`_', '`Contributing`', readme)
history = re.sub(r':mod:|:class:|:func:', '', open_as_utf('HISTORY.rst').read())


#def long_description():
#    with codecs.open('README.rst', encoding='utf8') as f:
#        return f.read()


setup(
    name='apibackuper',
    version=apibackuper.__version__,
    description=apibackuper.__doc__.strip(),
#    long_description=readme,
    long_description=readme + '\n\n' + history,
#    long_description=long_description(),
    long_description_content_type='text/x-rst',
    url='https://github.com/datacoon/apibackuper/',
    download_url='https://github.com/datacoon/apibackuper/',
    packages=find_packages(exclude=('tests', 'tests.*')),
    include_package_data=True,
    author=apibackuper.__author__,
    author_email='ivan@begtin.tech',
    license=apibackuper.__licence__,
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
