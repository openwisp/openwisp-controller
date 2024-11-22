#!/usr/bin/env python
from setuptools import find_packages, setup

from openwisp_controller import get_version


def get_install_requires():
    """
    parse requirements.txt, ignore links, exclude comments
    """
    requirements = []
    for line in open('requirements.txt').readlines():
        # skip to next iteration if comment or empty line
        if (
            line.startswith('#')
            or line == ''
            or line.startswith('http')
            or line.startswith('git')
        ):
            continue
        # add line to requirements
        requirements.append(line)
    return requirements


setup(
    name="openwisp-controller",
    version=get_version(),
    license="GPL3",
    author="OpenWISP",
    author_email="support@openwisp.io",
    description="OpenWISP Controller",
    long_description=open("README.rst").read(),
    url="http://openwisp.org",
    download_url="https://github.com/openwisp/openwisp-controller/releases",
    platforms=["Platform Independent"],
    keywords=["django", "netjson", "openwrt", "networking", "openwisp"],
    packages=find_packages(exclude=['tests*', 'docs*']),
    include_package_data=True,
    zip_safe=False,
    install_requires=get_install_requires(),
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: System :: Networking',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: OS Independent',
        'Framework :: Django',
        'Programming Language :: Python :: 3',
    ],
)
