import os

from setuptools import find_packages, setup

if os.path.isdir("/usr/local/etc/init.d"):
    _data = [('/usr/local/etc/init.d', ['rc.d/iocage'])]
else:
    _data = [('/usr/local/etc/rc.d', ['rc.d/iocage'])]

setup(name='iocage',
      version='0.9.5',
      description='A jail manager that uses ZFS.',
      author='Brandon Schneider and Peter Toth',
      author_email='brandon@ixsystems.com',
      url='https://github.com/iocage/iocage',
      packages=find_packages(),
      include_package_data=True,
      install_requires=[
          'click',
          'texttable',
          'backports.lzma',
          'requests',
          'tqdm',
          'future'
      ],
      entry_points={
          'console_scripts': [
              'iocage = iocage.main:main'
          ]
      },
      data_files=_data
      )
