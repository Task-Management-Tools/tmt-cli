# Expect external environment variables:
# - SOURCE_FILES: source files
# - TARGET_NAME: name of target (e.g. checker)
# - CXX: real C++ compiler name, default to g++
# - CXXFLAGS: C++ compilation flags
# - INCLUDE_PATHS: include paths (absolute path preferred)

# This can be override by environment variables
CXX ?= g++ 
CXXFLAGS := $(foreach dir, $(INCLUDE_PATHS), -I $(dir)) $(CXXFLAGS)
SHELL := /bin/bash

DEP = $(TARGET_NAME).d
EXE = $(TARGET_NAME)
LOG = $(TARGET_NAME).compile.log

all: $(EXE)

$(DEP): $(SOURCE_FILES)
	$(CXX) $(CXXFLAGS) -MM $^ -MT $(EXE) -MF $@

include $(DEP)

$(EXE): $(SOURCE_FILES)
	$(CXX) $(CXXFLAGS) -fdiagnostics-color=never $(SOURCE_FILES) -o $(EXE) 2> $(LOG)

clean:
	rm -f $(EXE) $(DEP) $(LOG)

logs: 
	@echo $(abspath $(LOG))
	
.PHONY: all clean
