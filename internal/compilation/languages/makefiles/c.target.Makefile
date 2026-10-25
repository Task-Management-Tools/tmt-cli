# Expect external environment variables:
# - SRCS: target source files
# - TARGET_NAME: target executable file
# - CC: real C compiler name, default to gcc
# - CFLAGS: C compilation flags
# - INCLUDE_PATHS: include paths (absolute path preferred)

# Set shell
SHELL := $(shell command -v bash)

# This can be overridden by environment variables
CC ?= gcc
INCPATHS := $(foreach dir, $(INCLUDE_PATHS), -I $(dir))
CFLAGS := $(CFLAGS)

DEP = build/$(TARGET_NAME).d
EXE = build/$(TARGET_NAME)
LOG = build/$(TARGET_NAME).compile.log

ifndef SRCS
$(error SRCS is undefined)
endif
ifndef TARGET_NAME
$(error TARGET_NAME is undefined)
endif

all: build $(EXE)

$(DEP): build
	$(CC) $(INCPATHS) -fdiagnostics-color=never -MM $(SRCS) $(CFLAGS) -MT $(EXE) -MF $@
include $(DEP)

$(EXE): $(SRCS)
	$(CC) $(INCPATHS) -fdiagnostics-color=never $(SRCS) $(CFLAGS) -o $(EXE) 2> $(LOG)

emit-log:
	@if [[ -f $(LOG) ]]; then \
		 cat $(LOG) >&2; \
	 else \
		 echo "warning: No such file: $$f" >&2; \
	 fi

build:
	[ -d build ] || mkdir build

# clean:
# 	rm -rf build

.PHONY: all emit-log
