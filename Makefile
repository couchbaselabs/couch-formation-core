.PHONY:	setup push pypi test
export PYTHONPATH := $(shell pwd)/test:$(shell pwd):$(PYTHONPATH)
export PROJECT_NAME := $$(basename $$(pwd))
export PROJECT_VERSION := $(shell cat VERSION)

commit:
		git commit -am "Version $(shell cat VERSION)"
		git push
build:
		bumpversion --allow-dirty build
patch:
		bumpversion --allow-dirty patch
minor:
		bumpversion --allow-dirty minor
major:
		bumpversion --allow-dirty major
setup:
		python setup.py sdist
push:
		$(eval REV_FILE := $(shell ls -tr dist/*.gz | tail -1))
		twine upload $(REV_FILE)
pypi: setup push
download:
		gh release create -R "mminichino/$(PROJECT_NAME)" \
		-t "Release $(PROJECT_VERSION)" \
		-n "Release $(PROJECT_VERSION)" \
		$(PROJECT_VERSION)
test_kvdb:
		python -m pytest tests/test_kvdb.py
test_aws:
		python -m pytest tests/test_1.py
test_gcp:
		python -m pytest tests/test_2.py
test_azure:
		python -m pytest tests/test_3.py
test:
		python -m pytest tests/test_1.py tests/test_2.py pytest tests/test_3.py
