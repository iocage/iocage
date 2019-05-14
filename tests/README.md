##### iocage must be installed for the tests to function

# Code testing
All the tests are written using the `pytest` unit testing framework. Code coverage is provided by `pytest-cov`

Before running tests, test dependencies can be installed by running:
```
$ pip3.6 install pytest-cov pytest-pep8 pytest-mock
```

## Unit tests

Located in the ``tests/unit_tests`` directory, they can be started as a normal user with the following command:

```
$ pytest
```

## Functional tests

Located in the ``tests/functional_tests``, they need a root access and the name of a ZFS pool

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
noupdate
    Decide whether or not to update the fetch to the latest patch level.
image
    Run the export and import operations.
```


# Example
- Follow [GitHub Installation in README.md](https://github.com/iocage/iocage/blob/master/README.md)
- cd iocage/iocage
- sudo pytest --zpool="TEST" --server="custom_server"
