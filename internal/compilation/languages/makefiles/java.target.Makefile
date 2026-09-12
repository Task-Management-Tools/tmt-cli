# Expect external environment variables:
# - SRCS: target source files
# - TARGET_NAME: target executable file
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

EXE = build/$(TARGET_NAME).jar
LOG = build/$(TARGET_NAME).compile.log
CLASS_DIR = build/$(TARGET_NAME).java-classes

ifndef SRCS
$(error SRCS is undefined)
endif
ifndef TARGET_NAME
$(error TARGET_NAME is undefined)
endif

all: build $(EXE)

$(EXE): $(SRCS)
	rm -rf $(CLASS_DIR)
	mkdir -p $(CLASS_DIR)
	$(JAVAC) $(JAVACFLAGS) -d $(CLASS_DIR) $(SRCS) 2> $(LOG)
	@MAIN_CLASSES="$$(find $(CLASS_DIR) -type f -name '*.class' -print \
		| sed -e 's#^$(CLASS_DIR)/##' -e 's#\.class$$##' -e 's#/#.#g' \
		| while IFS= read -r class_name; do \
			if $(JAVAP) -classpath $(CLASS_DIR) -public -s "$$class_name" 2> /dev/null \
				| awk '/public .*static .* main\(/ { getline; if ($$0 ~ /descriptor: \(\[Ljava\/lang\/String;\)V/) found=1 } END { exit !found }'; then \
				echo "$$class_name"; \
			fi; \
		done)"; \
	if [[ -z "$$MAIN_CLASSES" ]]; then \
		echo "error: No class containing a public static main method was found." >> $(LOG); \
		exit 1; \
	fi; \
	if [[ "$$(printf '%s\n' "$$MAIN_CLASSES" | wc -l)" -ne 1 ]]; then \
		echo "error: Multiple classes containing public static main methods were found:" >> $(LOG); \
		printf '%s\n' "$$MAIN_CLASSES" >> $(LOG); \
		exit 1; \
	fi; \
	$(JAR) cfe $@ "$$MAIN_CLASSES" -C $(CLASS_DIR) . 2>> $(LOG)
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
