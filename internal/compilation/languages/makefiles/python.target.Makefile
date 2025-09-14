# Expect external environment variables:
# - SRCS: target source files
# - TARGET_NAME: target executable file
# - PYTHON: real Python3 compiler name, default to python3

# Set shell
SHELL := /bin/bash

PYTHON ?= python3

EXE = build/$(TARGET_NAME).pyz
LOG = build/$(TARGET_NAME).compile.log

ifndef SRCS
$(error SRCS is undefined)
endif
ifndef TARGET_NAME
$(error TARGET_NAME is undefined)
endif

all: $(EXE) emit-log

$(EXE): $(SRCS)
	rm -rf build/python/
	mkdir -p build/python/
	cp $^ build/python/
	$(PYTHON) -m compileall build/python/ -b 2> build/$*.compile.log
	mv build/python/$(basename $<).pyc build/python/__main__.pyc
	zip $@ build/python/*.pyc
	rm -rf build/python/

emit-log:
	@if [[ -f $(LOG) ]]; then \
		 cat $(LOG) >&2; \
	 else \
		 echo "warning: No such file: $$f"; \
	 fi
	
.PHONY: all clean emit-log
