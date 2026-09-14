#!/bin/bash

set -euo pipefail

if [[ "$#" -ne 1 ]]; then
    echo "Usage: $(basename $0) <classes_dir>" >&2
    exit 1
fi

classes_dir="$1"

JAVA="${JAVA:-java}"

main_classes=$(
    find "$classes_dir" -type f -name '*.class' -print0 | \
    while IFS= read -r -d $'\0' file; do
        class_path=${file#"$classes_dir"/}
        class_base=${class_path%.class}
        class_name=${class_base//\//.}
        # Actually try to launch the class to see if it can be an entry point
        # This also works better for Java 25 with its broader `main`s
        if "$JAVA" --dry-run -classpath "$classes_dir" "$class_name" >/dev/null 2>&1; then
            echo "$class_name"
        fi
    done
)

# Only output the result if there is exactly one entry point class
# Here we use grep to count lines to handle trailing newlines correctly in all cases
classes_count=$(printf '%s' "$main_classes" | (grep -cF '' || true))
if [[ "$classes_count" -eq 0 ]]; then
    echo "error: No class containing a main method was found." >&2
    exit 1
fi
if [[ "$classes_count" -gt 1 ]]; then
    echo "error: Multiple classes containing main methods were found:" >&2
    echo "$main_classes" >&2
    exit 1
fi

echo "$main_classes"
