# Expect external environment variables:
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

SRCS = $(wildcard *.java)
EXES = $(SRCS:%.java=build/%.jar)
LOGS = $(SRCS:%.java=build/%.compile.log)

MAKEFILE_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
DETECT_MAIN_SCRIPT = $(MAKEFILE_DIR)/utils/java-detect-main.sh

all: build $(EXES)

build/%.jar: %.java build $(DETECT_MAIN_SCRIPT)
	rm -rf build/$*.java-classes
	mkdir -p build/$*.java-classes
	$(JAVAC) $(JAVACFLAGS) -d build/$*.java-classes $< 2> build/$*.compile.log
	MAIN_CLASS="$$(JAVA="$(JAVA)" $(DETECT_MAIN_SCRIPT) build/$*.java-classes 2>> build/$*.compile.log)" && \
		$(JAR) cfe $@ "$$MAIN_CLASS" -C build/$*.java-classes . 2>> build/$*.compile.log
	rm -rf build/$*.java-classes

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
