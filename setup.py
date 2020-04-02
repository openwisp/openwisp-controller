#!/usr/bin/env python
import os
import sys

from openwisp_controller import get_version
from setuptools import find_packages, setup

if sys.argv[-1] == 'publish':
    # delete any *.pyc, *.pyo and __pycache__
    os.system('find . | grep -E "(__pycache__|\.pyc|\.pyo$)" | xargs rm -rf')
    os.system("python setup.py sdist bdist_wheel")
    os.system("twine upload -s dist/*")
    os.system("rm -rf dist build")
    args = {'version': get_version()}
    print("You probably want to also tag the version now:")
    print("  git tag -a %(version)s -m 'version %(version)s'" % args)
    print("  git push --tags")
    sys.exit()


setup(
    name='openwisp-controller',
    version=get_version(),
    license='GPL3',
    author='Federico Capoano',
    author_email='federico.capoano@gmail.com',
    description='OpenWISP 2 Controller',
    long_description=open('README.rst').read(),
    url='http://openwisp.org',
    download_url='https://github.com/openwisp/openwisp-controller/releases',
    platforms=['Platform Independent'],
    keywords=['django', 'netjson', 'openwrt', 'networking', 'openwisp'],
    packages=find_packages(exclude=['tests', 'docs']),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        "django-netjsonconfig>=0.11.0,<0.12.0",
        "openwisp-users>=0.2.0,<0.3.0",
        "django-loci>=0.3.1,<0.4.0",
        "djangorestframework-gis>=0.12.0,<0.16.0",
        "paramiko>=2.4.1,<2.8.0",
        "scp>=0.13.0,<0.14.0",
        "celery>=4.2.0,<4.5.0",
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: System :: Networking',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: OS Independent',
        'Framework :: Django',
        'Programming Language :: Python :: 3',
    ]
)
