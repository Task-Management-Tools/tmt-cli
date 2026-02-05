# Expect external environment variables:
# - CXX: real C++ compiler name, default to g++
# - CXXFLAGS: C++ compilation flags
# - INCLUDE_PATHS: include paths (absolute path preferred)

# Set shell
SHELL := /bin/bash

CXX ?= g++
CXXFLAGS := $(foreach dir, $(INCLUDE_PATHS), -I $(dir)) $(CXXFLAGS)

# Find all C++ source files with different extensions
# TODO should we search for **/*.cpp ?
CPP_SOURCES = $(wildcard *.cpp)
CC_SOURCES = $(wildcard *.cc)

SRCS = $(CPP_SOURCES) $(CC_SOURCES)
EXES = $(CPP_SOURCES:%.cpp=build/%) $(CC_SOURCES:%.cc=build/%)
DEPS = $(CPP_SOURCES:%.cpp=build/%.d) $(CC_SOURCES:%.cc=build/%.d)
LOGS = $(CPP_SOURCES:%.cpp=build/%.compile.log) $(CC_SOURCES:%.cc=build/%.compile.log)

all: build $(EXES) emit-log

build/%.d: %.cpp build
	$(CXX) $(CXXFLAGS) -fdiagnostics-color=never -MM $< -MT $* -MF $@

build/%.d: %.cc build
	$(CXX) $(CXXFLAGS) -fdiagnostics-color=never -MM $< -MT $* -MF $@

include $(DEPS)

build/%: %.cpp
	$(CXX) $(CXXFLAGS) -fdiagnostics-color=never $< -o $@ 2> build/$*.compile.log

build/%: %.cc
	$(CXX) $(CXXFLAGS) -fdiagnostics-color=never $< -o $@ 2> build/$*.compile.log

build:
	[ -d build ] || mkdir build

# clean:
# 	rm -rf build

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
