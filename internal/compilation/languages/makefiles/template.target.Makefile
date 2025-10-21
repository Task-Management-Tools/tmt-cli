# Target Makefile should at least expect these external environment variables:
# - SRCS: target source files
# - TARGET_NAME: target executable file (basename, add extension if appropriate)

# Set shell
SHELL := /bin/bash

# All work should be done in the build directory
EXE = build/$(TARGET_NAME) # add extension if necessary
LOG = build/$(TARGET_NAME).compile.log

ifndef SRCS
$(error SRCS is undefined)
endif
ifndef TARGET_NAME
$(error TARGET_NAME is undefined)
endif

# Target all should emit-log at the end
all: build $(EXE) emit-log

# TODO: specify how to build target

emit-log:
	@if [[ -f $(LOG) ]]; then \
		 cat $(LOG) >&2; \
	 else \
		 echo "warning: No such file: $$f" >&2; \
	 fi

build:
	[ -d build ] || mkdir build

.PHONY: all emit-log
