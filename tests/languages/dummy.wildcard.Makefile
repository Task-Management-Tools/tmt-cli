# Set shell
SHELL := /bin/bash

SRCS = $(wildcard *.dummy)
EXES = $(SRCS:%.dummy=build/%)
LOGS = $(SRCS:%.dummy=build/%.compile.log)

all: build $(EXES)

build/%: %.dummy
	$(COMPILER) $< 2> build/$*.compile.log

build:
	[ -d build ] || mkdir build

emit-log:
	@for f in $(LOGS); do \
		if [[ -f $$f ]]; then \
			echo "---- $$f ----" >&2; \
			cat $$f >&2; \
		fi; \
	done

.PHONY: all emit-log
