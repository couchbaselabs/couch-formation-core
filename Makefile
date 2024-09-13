.PHONY:	pypi publish test commit patch minor major download remote_download remote
export LOGPATH := $(shell pwd)/tests/log
export PROJECT_NAME := $$(basename $$(pwd))
export PROJECT_VERSION := $(shell cat VERSION)
export TEST_PATH := $(shell pwd)/tests

commit:
		git commit -am "Version $(shell cat VERSION)"
		git push -u origin main
branch:
		git branch "Version_$(shell cat VERSION)"
merge:
		git checkout main
		git pull origin main
		git merge "Version_$(shell cat VERSION)"
		git push origin main
remote:
		git push cblabs main
patch:
		bumpversion --allow-dirty patch
minor:
		bumpversion --allow-dirty minor
major:
		bumpversion --allow-dirty major
setup:
		python setup.py sdist
twine:
		$(eval REV_FILE := $(shell ls -tr dist/*.gz | tail -1))
		twine upload $(REV_FILE)
pypi:
		poetry build
		poetry publish
publish:
		poetry publish
download:
		gh release create -R "mminichino/$(PROJECT_NAME)" \
		-t "Release $(PROJECT_VERSION)" \
		-n "Release $(PROJECT_VERSION)" \
		$(PROJECT_VERSION)
remote_download:
		gh release create -R "couchbaselabs/$(PROJECT_NAME)" \
		-t "Release $(PROJECT_VERSION)" \
		-n "Release $(PROJECT_VERSION)" \
		$(PROJECT_VERSION)
release: commit pypi download remote_download remote
container:
		docker system prune -f
		docker buildx prune -f
		docker buildx build --load --platform linux/amd64,linux/arm64 -t cftest -f $(TEST_PATH)/Dockerfile .
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
test_aws_install:
		python -m pytest tests/test_13.py
test_drv:
		python -m pytest tests/test_1.py tests/test_2.py tests/test_3.py tests/test_8.py
test_cli:
		python -m pytest tests/test_4.py tests/test_5.py tests/test_6.py tests/test_7.py pytest tests/test_9.py
test:
		mkdir -p $(LOGPATH)
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
		tests/test_10.py \
		tests/test_11.py \
		tests/test_kvdb.py
test_win:
		python -m pytest \
		tests/test_1.py \
		tests/test_2.py \
		tests/test_3.py \
		tests/test_4.py \
		tests/test_5.py \
		tests/test_6.py \
		tests/test_7.py \
		tests/test_8.py \
		tests/test_kvdb.py
test_install:
		python -m pytest \
		tests/test_12.py \
		tests/test_13.py \
		tests/test_14.py
