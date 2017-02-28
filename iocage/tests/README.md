# Code testing
All the tests are written using the `pytest` unit testing framework. Code coverage is provided by `pytest-cov`

Before running tests, test dependencies can be installed by running:
```
$ pip install pytest-cov pytest-pep8
```

## Unit tests

Located in the ``tests/unit_tests`` directory, they can be started as a normal user with the following command:

```
$ pytest
```

## Functional tests

Located in the ``tests/functional_tests``, they need a root acces and the name of a ZFS pool

**/!\ The contents of the specified ZFS pool will be destroyed**

To start the functional tests, run pytest with root privileges and the name of a zpool:
```
$ sudo pytest --zpool=mypool
```

Other parameters are available, to see them run:
```
$ pytest --fixtures
```
Extract:
```
zpool 
    Specify a zpool to use.
release 
    Specify a RELEASE to use.
server 
    FTP server to login to.
user 
    The user to use for fetching.
password 
    The password to use for fetching.
root_dir 
    Root directory containing all the RELEASEs for fetching.
http 
    Have --server define a HTTP server instead.
hardened 
    Have fetch expect the default HardeneBSD layout instead.
_file 
    Use a local file directory for root-dir instead of FTP or HTTP.
auth 
    Authentication method for HTTP fetching. Valid values: basic, digest
```


#Example
```
$ git clone https://github.com/iocage/iocage.git
$ cd iocage/iocage
$ sudo pytest --zpool="TEST" --server="custom_server"
```
