import sys

print(" ".join(sys.argv[2:]))
print("waterproof", file=open(sys.argv[1], "w"))
