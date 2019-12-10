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

get-test-data:
	python -m ginput.testing.test_utils get

check-test-data:
	python -m ginput.testing.test_utils check

update-test-hashes:
	python -m ginput.testing.test_utils up

.PHONY: test quicktest test-profiles test-utils get-test-data check-test-data update-test-hashes
