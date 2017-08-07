#!/usr/local/bin/python3.6
# -*- coding: utf-8 -*-

import re
import sys
import os

__dirname = os.path.dirname(__file__)
iocage_lib_dir = os.path.join(__dirname, "lib")
sys.path = [iocage_lib_dir] + sys.path


class Releases:

   def __new__(*args, **kwargs):
      import Releases
      return Releases.Releases(*args[1:], **kwargs)


class Release:

   def __new__(*args, **kwargs):
      import Release
      return Release.Release(*args[1:], **kwargs)


class Jails:

   def __new__(*args, **kwargs):
      import Jails
      return Jails.Jails(*args[1:], **kwargs)


class Jail:
   def __new__(*args, **kwargs):

      import Jail
      return Jail.Jail(*args[1:], **kwargs)


class Host:

   def __new__(*args, **kwargs):
      import Host
      return Host.Host(*args[1:], **kwargs)


class Logger:

   def __new__(*args, **kwargs):
      import Logger
      return Logger.Logger(*args[1:], **kwargs)
