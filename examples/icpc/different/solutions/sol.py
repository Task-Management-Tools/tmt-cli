import sys

for line in sys.stdin:
    a, b = line.split()
    print(abs(int(a) - int(b)))
