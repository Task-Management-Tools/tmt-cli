# Expect external environment variables:
# - SRCS: target source files
# - TARGET_NAME: target executable file
# - JAVAC: real Java compiler name, default to javac
# - JAVACFLAGS: Java compilation flags
# - JAVA: real Java launcher name, default to java
# - JAR: real Java archive tool name, default to jar

# Set shell
SHELL := $(shell command -v bash)

JAVAC ?= javac
JAVACFLAGS := $(JAVACFLAGS)
JAVA ?= java
JAR ?= jar

EXE = build/$(TARGET_NAME).jar
LOG = build/$(TARGET_NAME).compile.log
CLASS_DIR = build/$(TARGET_NAME).java-classes

MAKEFILE_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
DETECT_MAIN_SCRIPT = $(MAKEFILE_DIR)/utils/java-detect-main.sh

ifndef SRCS
$(error SRCS is undefined)
endif
ifndef TARGET_NAME
$(error TARGET_NAME is undefined)
endif

all: build $(EXE)

$(EXE): $(SRCS) $(DETECT_MAIN_SCRIPT)
	rm -rf $(CLASS_DIR)
	mkdir -p $(CLASS_DIR)
	$(JAVAC) $(JAVACFLAGS) -d $(CLASS_DIR) $(SRCS) 2> $(LOG)
	MAIN_CLASS="$$(JAVA="$(JAVA)" $(DETECT_MAIN_SCRIPT) $(CLASS_DIR) 2>> $(LOG))" && \
		$(JAR) cfe $@ "$$MAIN_CLASS" -C $(CLASS_DIR) . 2>> $(LOG)
	rm -rf $(CLASS_DIR)

emit-log:
	@if [[ -f $(LOG) ]]; then \
		cat $(LOG) >&2; \
	else \
		echo "warning: No such file: $$f" >&2; \
	fi

build:
	[ -d build ] || mkdir build

.PHONY: all emit-log
