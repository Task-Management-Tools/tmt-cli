object Lcg {
    private var current = 1
    operator fun invoke(): Int {
        current = ((current.toLong() * 100 + 20) % 998244353).toInt()
        return current
    }
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
        // There is no standard way in Kotlin to raise a POSIX signal, so create a generic error instead
        "runerror-signal", "runerror-sigxfsz", "runerror-sigxcpu" -> error("would be killed by a signal")
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
