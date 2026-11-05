import time
import signal

match input():
    case "correct":
        print("answer")
    case "wrong":
        print("not answer")
    case "empty":
        pass
    case "remove-stdout":
        pass  # skip this
    case "timeout-cpu":
        sum(range(10**10))
    case "timeout-wall":
        time.sleep(2.0)
    case "runerror-exit":
        exit(1)
    case "runerror-signal":
        signal.raise_signal(signal.SIGABRT)
    case "runerror-sigxfsz":
        signal.signal(signal.SIGXFSZ, signal.SIG_DFL)
        signal.raise_signal(signal.SIGXFSZ)
    case "runerror-sigxcpu":
        signal.raise_signal(signal.SIGXCPU)
    case "runerror-any":
        float("haha")
    case "memory-limit":
        big = [0] * (32 * 1024 * 1024)
        big[100] = 1
