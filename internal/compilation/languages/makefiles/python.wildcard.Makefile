# Expect external environment variables:
# - PYTHON: real Python3 compiler name, default to python3

# Set shell
SHELL := /bin/bash

PYTHON ?= python3

SRCS = $(wildcard *.py)
EXES = $(SRCS:%.py=build/%.pyz)
LOGS = $(SRCS:%.py=build/%.compile.log)

all: $(EXES) emit-log

build/%.pyz: %.py build
	cp $< build/
	$(PYTHON) -m compileall build/$< -b 2> build/$*.compile.log
	mv build/$*.pyc build/__main__.pyc
	zip -j $@ build/__main__.pyc
	rm build/__main__.pyc

build:
	mkdir -p build

emit-log:
	@for f in $(LOGS); do \
		echo "---- $$f ----"; \
		if [[ -f $$f ]]; then \
			cat $$f >&2; \
		else \
			echo "warning: compilation log file $$f does not exist"; \
		fi; \
	done

.PHONY: all emit-log
