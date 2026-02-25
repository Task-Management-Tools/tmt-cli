# Expect external environment variables:
# - PYTHON: real Python3 compiler name, default to python3

# Set shell
SHELL := /bin/bash

PYTHON ?= python3

SRCS = $(wildcard *.py)
EXES = $(SRCS:%.py=build/%.pyz)
LOGS = $(SRCS:%.py=build/%.compile.log)

all: $(EXES)

build/%.pyz: %.py build
	mkdir -p build/$*
	cp $< build/$*/__main__.py
	$(PYTHON) -m zipapp build/$* 2> build/$*.compile.log
	rm -r build/$*

build:
	mkdir -p build

emit-log:
	@for f in $(LOGS); do \
		if [[ -f $$f ]]; then \
			echo "---- $$f ----" >&2; \
			cat $$f >&2; \
		fi; \
	done

.PHONY: all emit-log
