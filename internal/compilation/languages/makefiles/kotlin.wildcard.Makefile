# Expect external environment variables:
# - KOTLINC: real Kotlin compiler name, default to kotlinc
# - KOTLINCFLAGS: Kotlin compilation flags

# Set shell
SHELL := $(shell command -v bash)

KOTLINC ?= kotlinc
KOTLINCFLAGS := $(KOTLINCFLAGS)

SRCS = $(wildcard *.kt)
EXES = $(SRCS:%.kt=build/%.jar)
LOGS = $(SRCS:%.kt=build/%.compile.log)

all: build $(EXES)

build/%.jar: %.kt build
	$(KOTLINC) $(KOTLINCFLAGS) $< -include-runtime -d $@ 2> build/$*.compile.log

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
