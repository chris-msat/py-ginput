ENV ?= ginput-py3

help:
	@cat .makehelp

install:
	./install.sh $(ENV)

test: test-profiles test-utils

quicktest: test-utils

test-profiles: 
	python -m ginput.testing.mod_maker_tests
	
test-utils:
	python -m ginput.testing.utility_tests

.PHONY: test quicktest test-profiles test-utils
