# Expect external environment variables:
# - CXX: real C++ compiler name, default to g++
# - CXXFLAGS: C++ compilation flags
# - INCPATHS: include paths (absolute path preferred)

CXX ?= g++
CXXFLAGS := $(foreach dir, $(INCPATHS), -I $(dir)) $(CXXFLAGS)
SHELL := /bin/bash

# Find all C++ source files with different extensions
# TODO should we search for **/*.cpp ?
CPP_SOURCES = $(wildcard *.cpp)
CC_SOURCES = $(wildcard *.cc)

SRCS = $(CPP_SOURCES) $(CC_SOURCES)
EXES = $(CPP_SOURCES:.cpp=.exe) $(CC_SOURCES:.cc=.exe)
DEPS = $(CPP_SOURCES:.cpp=.d) $(CC_SOURCES:.cc=.d)
LOGS = $(CPP_SOURCES:.cpp=.compile.log) $(CC_SOURCES:.cc=.compile.log)

all: $(EXES)

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

logs: 
	@echo $(abspath $(LOGS))

.PHONY: all clean
