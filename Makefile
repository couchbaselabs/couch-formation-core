.PHONY:	version setup push pypi test
export PYTHONPATH := $(shell pwd)/test:$(shell pwd):$(PYTHONPATH)

version:
		bumpversion patch
		git push
setup:
		python setup.py sdist
push:
		$(eval REV_FILE := $(shell ls -tr dist/*.gz | tail -1))
		twine upload $(REV_FILE)
pypi: setup push
test_aws:
		python -m pytest tests/test_1.py
test_gcp:
		python -m pytest tests/test_2.py
test:
		python -m pytest tests/test_1.py tests/test_2.py
