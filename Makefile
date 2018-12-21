ZPOOL=""
SERVER=""
PYTHON?=/usr/local/bin/python3

install:
	@test -s ${PYTHON} || (echo "Python path ${PYTHON} not found, please enter a valid one"; exit 1)
	@(pkg -vv | grep -e "url.*/latest") > /dev/null 2>&1 || (echo "Please ensure pkg url is using \"latest\" instead of \"quarterly\" in /etc/pkg/FreeBSD.conf before proceeding with installation"; exit 1)
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
