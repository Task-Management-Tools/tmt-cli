import sys
import re

line = sys.stdin.readline()

if line == "":
    print("The first line is empty", file=sys.stderr)
    exit(43)
if sys.stdin.readline() != "":
    print("Extra information in the input file", file=sys.stderr)
    exit(43)


if line[-1] != "\n":
    print("The first line does not end with a newline character", file=sys.stderr)
    exit(43)
line = line[:-1]

if line.count(" ") != 1:
    print("The first line should contain exactly one space", file=sys.stderr)
    exit(43)
a, b = line.split(" ")

number = re.compile(r"(0|[1-9]\d*)")
if not number.fullmatch(a) or not number.fullmatch(b):
    print("The tokens are not numbers", file=sys.stderr)
    exit(43)
if int(a) < 0 or 2_000_000_000 < int(a):
    print("Variable a is outside the range of [0, 2*10^9]", file=sys.stderr)
    exit(43)
if int(b) < 0 or 2_000_000_000 < int(b):
    print("Variable b is outside the range of [0, 2*10^9]", file=sys.stderr)
    exit(43)

exit(42)
