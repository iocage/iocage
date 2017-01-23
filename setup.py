from setuptools import find_packages, setup

setup(name='iocage',
      version='0.9.3',
      description='A jail manager that uses ZFS.',
      author='Brandon Schneider and Peter Toth',
      author_email='brandon@ixsystems.com',
      url='https://github.com/iocage/iocage',
      packages=find_packages(),
      include_package_data=True,
      install_requires=[
          'click',
          'tabletext',
          'backports.lzma',
          'requests',
          'tqdm'
      ],
      entry_points={
          'console_scripts': [
              'iocage = iocage.main:main'
          ]
      })
