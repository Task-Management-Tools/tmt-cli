object Lcg {
    private var current = 1
    operator fun invoke(): Int {
        current = ((current.toLong() * 100 + 20) % 998244353).toInt()
        return current
    }
}

// TODO: No portable way to raise POSIX signals in the program itself, or setting handlers
// There's a proprietary API sun.misc.Signal but it's unsupported and deprecated
fun raiseSignal(name: String) {
    // OpenJDK by default ignores SIGXFSZ, but the intended behavior is to die
    if (name == "XFSZ") error("fake OLE")
    val pid = ProcessHandle.current().pid()
    ProcessBuilder("kill", "-$name", pid.toString()).start().waitFor()
}

fun main() {
    when (readln()) {
        "correct" -> println("answer")
        "wrong" -> println("not answer")
        "empty" -> Unit
        "remove-stdout" -> Unit
        "timeout-cpu" -> {
            var sum = 0L
            repeat(1_000_000_000) {
                sum += Lcg()
            }
            println(sum)
        }
        "timeout-wall" -> Thread.sleep(2_000)
        "runerror-exit" -> kotlin.system.exitProcess(1)
        "runerror-signal" -> raiseSignal("ABRT")
        "runerror-sigxfsz" -> raiseSignal("XFSZ")
        "runerror-sigxcpu" -> raiseSignal("XCPU")
        "runerror-any" -> error("test error")
        "memory-limit" -> {
            val largeMemory = IntArray(64 * 1024 * 1024)
            for (i in largeMemory.indices step 1024) {
                largeMemory[i] = Lcg()
            }
            println(largeMemory[67])
        }
    }
}
