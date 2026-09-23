import time

run = int(input())
if run < 3:
    now = time.monotonic()
    while time.monotonic() - now < 0.6:
        pass
    print("keep")
else:
    print("accept")
