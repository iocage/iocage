ZPOOL=""
SERVER=""
SRC_BASE?="/usr/src"

install:
	echo -e "import os\ntry:\n  if not os.listdir('$(SRC_BASE)'): exit('$(SRC_BASE) must be populated!')\nexcept FileNotFoundError:\n  exit('$(SRC_BASE) must be populated!')" | python3.6
	test -d .git && git pull || true
	python3.6 -m ensurepip
	pip3.6 install -U Cython
	export FREEBSD_SRC=$(SRC_BASE) && cd py-libzfs && python3.6 setup.py build && python3.6 setup.py install
	pkg install -q -y libgit2
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
