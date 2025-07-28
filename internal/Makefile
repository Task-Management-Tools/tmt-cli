# Compiler and flags
CXX = g++ # TODO find real g++ for mac users
CXXFLAGS := -I ../include $(CXXFLAGS) # TODO not to use .. 
SHELL := /bin/bash

# Find all C++ source files with different extensions
# TODO should we search for **/*.cpp ?
CPP_SOURCES = $(wildcard *.cpp)
CC_SOURCES = $(wildcard *.cc)

SOURCES = $(CPP_SOURCES) $(CC_SOURCES)
EXECUTABLES = $(CPP_SOURCES:.cpp=.exe) $(CC_SOURCES:.cc=.exe)

all: $(EXECUTABLES)

# Only supports single-file mode

%.exe: %.cpp
	$(CXX) $(CXXFLAGS) -fdiagnostics-color=never $< -o $@ 2> ._$*.compile.log

%.exe: %.cc
	$(CXX) $(CXXFLAGS) -fdiagnostics-color=never $< -o $@ 2> ._$*.compile.log

clean:
	rm -f $(EXECUTABLES)

.PHONY: all clean

# Debug target - show what files will be compiled
debug:
	@echo "Source files: $(SOURCES)"
	@echo "Executables: $(EXECUTABLES)"
	@echo "CXXFLAGS: $(CXXFLAGS)"
