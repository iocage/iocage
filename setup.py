import os

import sys
import fastentrypoints
from setuptools import find_packages, setup

if os.path.isdir("/usr/local/etc/init.d"):
    _data = [('/usr/local/etc/init.d', ['rc.d/iocage']),
             ('/usr/local/man/man8', ['iocage/iocage.8.gz'])]
else:
    _data = [('/usr/local/etc/rc.d', ['rc.d/iocage']),
             ('/usr/local/man/man8', ['iocage/iocage.8.gz'])]

if sys.version_info < (3, 6):
    exit("Only Python 3.6 and higher is supported.")

setup(name='iocage',
      version='0.9.8.1',
      description='A jail manager that uses ZFS.',
      author='Brandon Schneider and Peter Toth',
      author_email='brandon@ixsystems.com',
      url='https://github.com/iocage/iocage',
      packages=find_packages(),
      include_package_data=True,
      install_requires=[
          'click',
          'texttable',
          'requests',
          'tqdm',
          'coloredlogs',
          'pygit2==0.24.2',
          'libzfs'
      ],
      setup_requires=['pytest-runner'],
      entry_points={
          'console_scripts': [
              'iocage = iocage.main:cli'
          ]
      },
      data_files=_data,
      tests_require=['pytest', 'pytest-cov', 'pytest-pep8']
      )
