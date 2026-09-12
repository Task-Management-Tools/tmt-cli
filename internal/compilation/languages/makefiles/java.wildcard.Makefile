# Expect external environment variables:
# - JAVAC: real Java compiler name, default to javac
# - JAVACFLAGS: Java compilation flags
# - JAR: real Java archive tool name, default to jar
# - JAVAP: real Java class disassembler name, default to javap

# Set shell
SHELL := $(shell command -v bash)

JAVAC ?= javac
JAR ?= jar
JAVAP ?= javap
JAVACFLAGS := $(JAVACFLAGS)

SRCS = $(wildcard *.java)
EXES = $(SRCS:%.java=build/%.jar)
LOGS = $(SRCS:%.java=build/%.compile.log)

all: build $(EXES)

build/%.jar: %.java build
	rm -rf build/$*.java-classes
	mkdir -p build/$*.java-classes
	$(JAVAC) $(JAVACFLAGS) -d build/$*.java-classes $< 2> build/$*.compile.log
	@MAIN_CLASSES="$$(find build/$*.java-classes -type f -name '*.class' -print \
		| sed -e 's#^build/$*.java-classes/##' -e 's#\.class$$##' -e 's#/#.#g' \
		| while IFS= read -r class_name; do \
			if $(JAVAP) -classpath build/$*.java-classes -public -s "$$class_name" 2> /dev/null \
				| awk '/public .*static .* main\(/ { getline; if ($$0 ~ /descriptor: \(\[Ljava\/lang\/String;\)V/) found=1 } END { exit !found }'; then \
				echo "$$class_name"; \
			fi; \
		done)"; \
	if [[ -z "$$MAIN_CLASSES" ]]; then \
		echo "error: No class containing a public static main method was found." >> build/$*.compile.log; \
		exit 1; \
	fi; \
	if [[ "$$(printf '%s\n' "$$MAIN_CLASSES" | wc -l)" -ne 1 ]]; then \
		echo "error: Multiple classes containing public static main methods were found:" >> build/$*.compile.log; \
		printf '%s\n' "$$MAIN_CLASSES" >> build/$*.compile.log; \
		exit 1; \
	fi; \
	$(JAR) cfe $@ "$$MAIN_CLASSES" -C build/$*.java-classes . 2>> build/$*.compile.log
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
