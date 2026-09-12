# Expect external environment variables:
# - SRCS: target source files
# - TARGET_NAME: target executable file
# - KOTLINC: real Kotlin compiler name, default to kotlinc
# - KOTLINCFLAGS: Kotlin compilation flags

# Set shell
SHELL := $(shell command -v bash)

KOTLINC ?= kotlinc
KOTLINCFLAGS := $(KOTLINCFLAGS)

EXE = build/$(TARGET_NAME).jar
LOG = build/$(TARGET_NAME).compile.log

ifndef SRCS
$(error SRCS is undefined)
endif
ifndef TARGET_NAME
$(error TARGET_NAME is undefined)
endif

all: build $(EXE)

$(EXE): $(SRCS)
	$(KOTLINC) $(KOTLINCFLAGS) $(SRCS) -include-runtime -d $@ 2> $(LOG)

emit-log:
	@if [[ -f $(LOG) ]]; then \
		cat $(LOG) >&2; \
	else \
		echo "warning: No such file: $$f" >&2; \
	fi

build:
	[ -d build ] || mkdir build

.PHONY: all emit-log
