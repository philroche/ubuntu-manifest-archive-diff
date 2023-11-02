#!/usr/bin/env python

"""The setup script."""

from setuptools import setup, find_packages

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

requirements = ['Click>=7.0', 'launchpadlib', 'python-debian', 'requests', ]

test_requirements = ['pytest>=3', ]

setup(
    author="Phil Roche",
    author_email='phil.roche@canonical.com',
    python_requires='>=3.6',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    description="Tool to compare a package manifest to the versions of the packages currently in the Ubuntu archive.",
    entry_points={
        'console_scripts': [
            'ubuntu-manifest-archive-diff=ubuntu_manifest_archive_diff.cli:ubuntu_manifest_archive_diff',
        ],
    },
    install_requires=requirements,
    license="GNU General Public License v3",
    long_description=readme + '\n\n' + history,
    include_package_data=True,
    keywords='ubuntu_manifest_archive_diff',
    name='ubuntu_manifest_archive_diff',
    packages=find_packages(include=['ubuntu_manifest_archive_diff', 'ubuntu_manifest_archive_diff.*']),
    test_suite='tests',
    tests_require=test_requirements,
    url='https://github.com/philroche/ubuntu_manifest_archive_diff',
    version='0.0.1',
    zip_safe=False,
)
