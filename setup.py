# Copyright (c) 2014-2017, iocage
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
import os
import sys

from setuptools import find_packages, setup

import fastentrypoints

if os.path.isdir("/".join([sys.prefix, "etc/init.d"])):
    _data = [('etc/init.d', ['rc.d/iocage']),
             ('man/man8', ['iocage/iocage.8.gz'])]
else:
    _data = [('etc/rc.d', ['rc.d/iocage']),
             ('man/man8', ['iocage/iocage.8.gz'])]

if os.path.isdir("/".join([sys.prefix, "share/zsh/site-functions/"])):
    _data.append(
        ('share/zsh/site-functions', ['zsh-completion/_iocage']))

if sys.version_info < (3, 6):
    exit("Only Python 3.6 and higher is supported.")

setup(
    name='iocage',
    version='1.0a',
    description='A jail manager that uses ZFS.',
    author='iocage Contributors',
    author_email='https://groups.google.com/forum/#!forum/iocage',
    url='https://github.com/iocage/iocage',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'click==6.7', 'texttable==0.9.0', 'requests==2.17.3',
        'coloredlogs==7.0', 'dulwich', 'libzfs'
    ],
    setup_requires=['pytest-runner'],
    entry_points={'console_scripts': ['iocage = iocage.main:cli']},
    data_files=_data,
    tests_require=['pytest', 'pytest-cov', 'pytest-pep8'])
