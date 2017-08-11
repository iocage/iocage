ZPOOL=""
SERVER=""

install:
	echo -e "import os\ntry:\n  if not os.listdir('/usr/src'): exit('/usr/src must be populated!')\nexcept FileNotFoundError:\n  exit('/usr/src must be populated!')" | python3.6
	git pull
	python3.6 -m ensurepip
	pip3.6 install -U Cython
	cd py-libzfs && python3.6 setup.py build && python3.6 setup.py install
	pkg install -q -y libgit2
	gzip --keep --force man/iocage.8.gz
	pip3.6 install -U .
uninstall:
	pip3.6 uninstall -y iocage
test:
	pytest --zpool $(ZPOOL) --server $(SERVER)
help:
	@echo "    install"
	@echo "        Installs iocage"
	@echo "    uninstall"
	@echo "        Removes iocage."
	@echo "    test"
	@echo "        Run unit tests with pytest"
