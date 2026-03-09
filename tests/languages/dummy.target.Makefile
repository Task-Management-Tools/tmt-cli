# Expect external environment variables:
# - SRCS: target source files
# - TARGET_NAME: target executable file

# Set shell
SHELL := /bin/bash

EXE = build/$(TARGET_NAME)
LOG = build/$(TARGET_NAME).compile.log

ifndef SRCS
$(error SRCS is undefined)
endif
ifndef TARGET_NAME
$(error TARGET_NAME is undefined)
endif

all: build $(EXE)

$(EXE): $(SRCS)
	$(COMPILER) $(SRCS) 2> $(LOG)

emit-log:
	@if [[ -f $(LOG) ]]; then \
		 cat $(LOG) >&2; \
	 else \
		 echo "warning: No such file: $$f" >&2; \
	 fi

build:
	[ -d build ] || mkdir build
	
.PHONY: all emit-log
