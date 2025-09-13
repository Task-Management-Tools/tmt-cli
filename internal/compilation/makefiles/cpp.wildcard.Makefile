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
EXES = $(CPP_SOURCES:.cpp=.exe) $(CC_SOURCES:.cc=.exe)
DEPS = $(CPP_SOURCES:.cpp=.d) $(CC_SOURCES:.cc=.d)
LOGS = $(CPP_SOURCES:.cpp=.compile.log) $(CC_SOURCES:.cc=.compile.log)

all: $(EXES) emit-log

%.d: %.cpp
	$(CXX) $(CXXFLAGS) -MM $< -MT $*.exe -MF $@

%.d: %.cc
	$(CXX) $(CXXFLAGS) -MM $< -MT $*.exe -MF $@

include $(DEPS)

%.exe: %.cpp
	$(CXX) $(CXXFLAGS) -fdiagnostics-color=never $< -o $@ 2> $*.compile.log

%.exe: %.cc
	$(CXX) $(CXXFLAGS) -fdiagnostics-color=never $< -o $@ 2> $*.compile.log

clean:
	rm -f $(EXES) $(DEPS) $(LOGS)

emit-log:
	@for f in $(LOGS); do \
		echo "---- $$f ----"; \
		if [[ -f $$f ]]; then \
			cat $$f; \
		else \
			echo "warning: compilation log file $$f does not exist"; \
		fi; \
	done

logs: 
	@echo $(abspath $(LOGS))

.PHONY: all clean emit-log
