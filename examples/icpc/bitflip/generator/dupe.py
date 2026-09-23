from pathlib import Path
import sys

# Not recommended but currently the only way to do this
testcase = list(Path(".").glob("*.in"))[0]
answer = testcase.with_suffix(".ans")

try:
    with open(answer, "w") as f:
        while line := sys.stdin.readline():
            sys.stdout.write(line)
            f.write(line)
except EOFError:
    pass
