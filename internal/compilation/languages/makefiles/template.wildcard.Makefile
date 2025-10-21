# Target Makefile only expects compiler environment variables

# Set shell
SHELL := /bin/bash

# All work should be done in the build directory
EXES = TODO # add extension if necessary
LOGS = TODO.compile.log

all: build $(EXES) emit-log

# TODO: specify how to build targets

build:
	[ -d build ] || mkdir build

emit-log:
	@for f in $(LOGS); do \
		echo "---- $$f ----" >&2; \
		if [[ -f $$f ]]; then \
			cat $$f >&2; \
		else \
			echo "warning: compilation log file $$f does not exist"; \
		fi; \
	done

.PHONY: all emit-log
