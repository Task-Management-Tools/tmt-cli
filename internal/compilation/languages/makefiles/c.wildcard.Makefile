# Expect external environment variables:
# - CC: real C compiler name, default to g++
# - CFLAGS: C compilation flags
# - INCLUDE_PATHS: include paths (absolute path preferred)

# Set shell
SHELL := $(shell command -v bash)

CC ?= g++
INCPATHS := $(foreach dir, $(INCLUDE_PATHS), -I $(dir))
CFLAGS := $(CFLAGS)

SRCS = $(wildcard *.c)
EXES = $(CPP_SOURCES:%.c=build/%)
DEPS = $(CPP_SOURCES:%.c=build/%.d)
LOGS = $(CPP_SOURCES:%.c=build/%.compile.log)

all: build $(EXES)

build/%.d: %.c build
	$(CC) $(INCPATHS) -fdiagnostics-color=never -MM $< $(CFLAGS) -MT $* -MF $@

include $(DEPS)

build/%: %.c
	$(CC) $(INCPATHS) -fdiagnostics-color=never $< $(CFLAGS) -o $@ 2> build/$*.compile.log

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
