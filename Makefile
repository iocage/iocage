ZPOOL=""
SERVER=""
PYTHON?=/usr/local/bin/python3

install:
	@(grep latest /etc/pkg/FreeBSD.conf) > /dev/null 2>&1 || (echo "Please ensure pkg url is using \"latest\" instead of \"quarterly\" in /etc/pkg/FreeBSD.conf before proceeding with installation"; exit 1)
	${PYTHON} -m ensurepip
	pkg install -y devel/py-libzfs
	${PYTHON} -m pip install -Ur requirements.txt .
uninstall:
	${PYTHON} -m pip uninstall -y iocage-lib iocage-cli
test:
	pytest --zpool $(ZPOOL) --server $(SERVER)
help:
	@echo "    install"
	@echo "        Installs iocage"
	@echo "    uninstall"
	@echo "        Removes iocage"
	@echo "    test"
	@echo "        Run unit tests with pytest"
