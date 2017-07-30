#!/usr/local/bin/python3.6
# -*- coding: utf-8 -*-

import re
import sys
import os

__dirname = os.path.dirname(__file__)
iocage_lib_dir = os.path.join(__dirname, "lib")
sys.path = [iocage_lib_dir] + sys.path

class Releases:
 def __new__(self, **kwargs):
   import Releases
   return Releases.Releases(**kwargs)

class Release:
 def __new__(self, **kwargs):
   import Releases
   return Releases.Releases(**kwargs)

class Jails:
 def __new__(self, **kwargs):
   import Jails
   return Jails.Jails(**kwargs)

class Jail:
 def __new__(self, **kwargs):
   import Jail
   return Jail.Jail(**kwargs)

class Host:
 def __new__(self, **kwargs):
   import Host
   return Host.Host(**kwargs)

class Logger:
 def __new__(self, **kwargs):
   import Logger
   return Logger.Logger(**kwargs)
