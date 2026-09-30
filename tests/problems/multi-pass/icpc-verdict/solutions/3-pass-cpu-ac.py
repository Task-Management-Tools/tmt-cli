import time

now = time.monotonic()
while time.monotonic() - now < 0.4:
    pass

run = int(input())
if run < 3:
    print("keep")
else:
    print("accept")
