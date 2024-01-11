.PHONY:	setup push pypi test
export PYTHONPATH := $(shell pwd)/test:$(shell pwd):$(PYTHONPATH)
export PROJECT_NAME := $$(basename $$(pwd))
export PROJECT_VERSION := $(shell cat VERSION)

commit:
		git commit -am "Version $(shell cat VERSION)"
		git push
branch:
		git checkout -b "Version_$(shell cat VERSION)"
		git push --set-upstream origin "Version_$(shell cat VERSION)"
merge:
		git checkout main
		git pull origin main
		git merge "Version_$(shell cat VERSION)"
		git push origin main
remote:
		git push cblabs main
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
test_aws_drv:
		python -m pytest tests/test_1.py
test_gcp_drv:
		python -m pytest tests/test_2.py
test_azure_drv:
		python -m pytest tests/test_3.py
test_aws_cli:
		python -m pytest tests/test_4.py
test_gcp_cli:
		python -m pytest tests/test_5.py
test_azure_cli:
		python -m pytest tests/test_6.py
test_capella_cli:
		python -m pytest tests/test_7.py
test_docker_drv:
		python -m pytest tests/test_8.py
test_docker_cli:
		python -m pytest tests/test_9.py
test_drv:
		python -m pytest tests/test_1.py tests/test_2.py tests/test_3.py tests/test_8.py
test_cli:
		python -m pytest tests/test_4.py tests/test_5.py tests/test_6.py tests/test_7.py pytest tests/test_9.py
test:
		python -m pytest \
		tests/test_1.py \
		tests/test_2.py \
		tests/test_3.py \
		tests/test_4.py \
		tests/test_5.py \
		tests/test_6.py \
		tests/test_7.py \
		tests/test_8.py \
		tests/test_9.py \
		tests/test_kvdb.py
