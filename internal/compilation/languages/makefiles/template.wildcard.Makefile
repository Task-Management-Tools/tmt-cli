# Target Makefile only expects compiler environment variables

# Set shell
SHELL := /bin/bash

# All work should be done in the build directory
EXES = TODO # add extension if necessary
LOGS = TODO.compile.log

all: build $(EXES)

# TODO: specify how to build targets

build:
	[ -d build ] || mkdir build

emit-log:
	@for f in $(LOGS); do \
		if [[ -f $$f ]]; then \
			echo "---- $$f ----" >&2; \
			cat $$f >&2; \
		fi; \
	done

.PHONY: all emit-log
