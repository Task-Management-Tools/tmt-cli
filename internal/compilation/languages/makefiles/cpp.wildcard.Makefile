# Expect external environment variables:
# - CXX: real C++ compiler name, default to g++
# - CXXFLAGS: C++ compilation flags
# - INCLUDE_PATHS: include paths (absolute path preferred)

# Set shell
SHELL := /bin/bash

CXX ?= g++
INCPATHS := $(foreach dir, $(INCLUDE_PATHS), -I $(dir))
CXXFLAGS := $(CXXFLAGS)

# Find all C++ source files with different extensions
# TODO should we search for **/*.cpp ?
CPP_SOURCES = $(wildcard *.cpp)
CC_SOURCES = $(wildcard *.cc)

SRCS = $(CPP_SOURCES) $(CC_SOURCES)
EXES = $(CPP_SOURCES:%.cpp=build/%) $(CC_SOURCES:%.cc=build/%)
DEPS = $(CPP_SOURCES:%.cpp=build/%.d) $(CC_SOURCES:%.cc=build/%.d)
LOGS = $(CPP_SOURCES:%.cpp=build/%.compile.log) $(CC_SOURCES:%.cc=build/%.compile.log)

all: build $(EXES)

build/%.d: %.cpp build
	$(CXX) $(INCPATHS) -fdiagnostics-color=never -MM $< $(CXXFLAGS) -MT $* -MF $@

build/%.d: %.cc build
	$(CXX) $(INCPATHS) -fdiagnostics-color=never -MM $< $(CXXFLAGS) -MT $* -MF $@

include $(DEPS)

build/%: %.cpp
	$(CXX) $(INCPATHS) -fdiagnostics-color=never $< $(CXXFLAGS) -o $@ 2> build/$*.compile.log

build/%: %.cc
	$(CXX) $(INCPATHS) -fdiagnostics-color=never $< $(CXXFLAGS) -o $@ 2> build/$*.compile.log

build:
	[ -d build ] || mkdir build

# clean:
# 	rm -rf build

emit-log:
	@for f in $(LOGS); do \
		if [[ -f $$f ]]; then \
			echo "---- $$f ----" >&2; \
			cat $$f >&2; \
		fi; \
	done

.PHONY: all emit-log
