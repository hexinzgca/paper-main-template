.DEFAULT_GOAL := help
PYTHON ?= python3
export PYTHONDONTWRITEBYTECODE := 1
export BASE_REV
export REASON

.PHONY: help compile check check-history check-dependencies test submodules code-test figures record-pins manifest release-manifest
help:
	@echo "compile | check | check-history | check-dependencies | test | submodules"
	@echo "code-test | figures | record-pins REASON='...' | manifest | release-manifest"
compile:
	$(PYTHON) scripts/manage.py compile
check:
	$(PYTHON) scripts/manage.py check
check-history:
	$(PYTHON) scripts/manage.py check --history
check-dependencies:
	$(PYTHON) scripts/manage.py check --require-submodules

test:
	$(PYTHON) -m unittest discover -s tests -v
submodules:
	$(PYTHON) scripts/manage.py submodules
code-test:
	$(PYTHON) scripts/manage.py code-test
figures:
	$(PYTHON) scripts/manage.py figures
record-pins:
	$(PYTHON) scripts/manage.py record-pins
manifest:
	$(PYTHON) scripts/manage.py manifest
release-manifest:
	$(PYTHON) scripts/manage.py manifest --release
