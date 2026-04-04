import sys

sys.modules["grader"] = sys.modules[__name__]

called_graderfunc = False


def graderfunc():
    global called_graderfunc
    called_graderfunc = True


assert input() == "input"

import gradertest

gradertest.userfunc()

if called_graderfunc:
    print("called graderfunc")
