# Running tests:
================
**These tests are written for `pytest`**

- Make sure you're in the iocage directory
- Supply --zpool="POOL" to pytest

#####Example:
```
git clone https://github.com/iocage/iocage.git
cd iocage/iocage
sudo pytest --zpool="TEST" --server="custom_server"
```

**To list all supported fixtures to pytest:**
`pytest --fixtures`
