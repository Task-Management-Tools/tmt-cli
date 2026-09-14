import java.io.IOException;
import java.util.Scanner;

class Lcg {
    private int current = 1;
    int next() {
        current = (int) (((long) current * 100 + 20) % 998244353);
        return current;
    }
}

class Main {
    // TODO: No portable way to raise POSIX signals in the program itself, or setting handlers
    // There's a proprietary API sun.misc.Signal but it's unsupported and deprecated
    private static void raiseSignal(String name) throws InterruptedException, IOException {
        // OpenJDK by default ignores SIGXFSZ, but the intended behavior is to die
        if (name == "XFSZ") {
            throw new IOException("fake OLE");
        }
        long pid = ProcessHandle.current().pid();
        new ProcessBuilder("kill", "-" + name, Long.toString(pid)).start().waitFor();
    }

    public static void main(String[] args) throws Exception {
        Scanner scanner = new Scanner(System.in);
        Lcg lcg = new Lcg();
        switch (scanner.nextLine()) {
            case "correct":
                System.out.println("answer");
                break;
            case "wrong":
                System.out.println("not answer");
                break;
            case "empty":
            case "remove-stdout":
                break;
            case "timeout-cpu": {
                long sum = 0;
                for (int i = 0; i < 1_000_000_000; ++i) {
                    sum += lcg.next();
                }
                System.out.println(sum);
                break;
            }
            case "timeout-wall":
                Thread.sleep(2_000);
                break;
            case "runerror-exit":
                System.exit(1);
                break;
            case "runerror-signal":
                raiseSignal("ABRT");
                break;
            case "runerror-sigxfsz":
                raiseSignal("XFSZ");
                break;
            case "runerror-sigxcpu":
                raiseSignal("XCPU");
                break;
            case "runerror-any":
                throw new RuntimeException("test error");
            case "memory-limit": {
                int[] largeMemory = new int[64 * 1024 * 1024];
                for (int i = 0; i < largeMemory.length; i += 1024) {
                    largeMemory[i] = lcg.next();
                }
                System.out.println(largeMemory[67]);
                break;
            }
            default:
                break;
        }
    }
}
