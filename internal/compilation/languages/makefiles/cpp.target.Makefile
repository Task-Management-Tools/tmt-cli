# Expect external environment variables:
# - SRCS: target source files
# - TARGET_NAME: target executable file
# - CXX: real C++ compiler name, default to g++
# - CXXFLAGS: C++ compilation flags
# - INCLUDE_PATHS: include paths (absolute path preferred)

# Set shell
SHELL := /bin/bash

# This can be overridden by environment variables
CXX ?= g++
CXXFLAGS := $(foreach dir, $(INCLUDE_PATHS), -I $(dir)) $(CXXFLAGS)

DEP = build/$(TARGET_NAME).d
EXE = build/$(TARGET_NAME)
LOG = build/$(TARGET_NAME).compile.log

ifndef SRCS
$(error SRCS is undefined)
endif
ifndef TARGET_NAME
$(error TARGET_NAME is undefined)
endif

all: build $(EXE) emit-log

$(DEP): build
	$(CXX) $(CXXFLAGS) -fdiagnostics-color=never -MM $(SRCS) -MT $(EXE) -MF $@
include $(DEP)

$(EXE): $(SRCS)
	$(CXX) $(CXXFLAGS) -fdiagnostics-color=never $(SRCS) -o $(EXE) 2> $(LOG)

emit-log:
	@if [[ -f $(LOG) ]]; then \
		 cat $(LOG) >&2; \
	 else \
		 echo "warning: No such file: $$f"; \
	 fi

build:
	[ -d build ] || mkdir build

# clean:
# 	rm -rf build
	
.PHONY: all emit-log
