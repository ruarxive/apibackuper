# This is purely the result of trial and error.

import io
import codecs
import re
import os

from setuptools import setup, find_packages

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

install_requires = [
    'typer', 'lxml', 'urllib3', 'requests', 'xmltodict', 'PyYAML', 'jsonschema>=4.0.0', 'tqdm>=4.66.0',
    'zstandard>=0.22.0',
]


extras_require = {}



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
    zip_safe=False,
    keywords='api json jsonl csv bson cli dataset',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Topic :: Software Development',
        'Topic :: System :: Networking',
        'Topic :: Terminals',
        'Topic :: Text Processing',
        'Topic :: Utilities'
    ],
)
