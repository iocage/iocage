ZPOOL=""
SERVER=""
SRC_BASE?="/usr/src"

install:
	test -d .git && git submodule init && git submodule update || true
	python3.6 -m ensurepip
	python3.6 -m pip install -U .
	test -d .git && cd libiocage && make install
uninstall:
	python3.6 -m pip uninstall -y iocage-lib iocage-cli
	cd libiocage && make uninstall
test:
	pytest --zpool $(ZPOOL) --server $(SERVER)
help:
	@echo "    install"
	@echo "        Installs iocage"
	@echo "    uninstall"
	@echo "        Removes iocage."
	@echo "    test"
	@echo "        Run unit tests with pytest"
