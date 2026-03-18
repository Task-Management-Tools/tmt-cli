#include <iostream>
#include <string>
#include <thread>
#include <chrono>
#include <csignal>
#include <cstdlib>

using namespace std::chrono_literals;

#include <climits> // for PATH_MAX
#include <cstring>
#include <iostream>
#include <string>
#include <sys/stat.h>
#include <unistd.h>

// Conditional includes for platform-specific headers
#if defined(__APPLE__)
#include <sys/fcntl.h>
#endif

void remove_stdout();

int main()
{
    std::string input;
    std::cin >> input;

    auto lcg = [current = 1] mutable {
        int mul = 100, shift = 20, modulo = 998244353;
        return (current = ((long long)current * mul + shift) % modulo);
    };

    if (input == "correct")
        std::cout << "answer\n";
    if (input == "wrong")
        std::cout << "not answer\n";
    if (input == "empty")
        std::cout << std::flush;
    if (input == "remove-stdout")
        remove_stdout();
    if (input == "timeout-cpu")
    {
        // Do a non-trivial computation
        long long sum = 0;
        for (int i = 0; i < 1'000'000'000; i++)
            sum += lcg();
        std::cout << sum << '\n';
    }
    if (input == "timeout-wall")
        std::this_thread::sleep_for(1s);
    if (input == "runerror-exit")
        std::exit(1);
    if (input == "runerror-signal")
        std::raise(SIGABRT);
    if (input == "runerror-sigxfsz")
        std::raise(SIGXFSZ);
    if (input == "runerror-sigxcpu")
        std::raise(SIGXCPU);
    if (input == "runerror-any")
        throw std::bad_alloc();
    if (input == "memory-limit")
    {
        // 4096 * 256 bytes
        int *large_mem = static_cast<int *>(std::malloc(256 * 1024 * 1024));
        for (int i = 0; i < 256 * 1024 * 1024 / sizeof(int); i += 1024)
            large_mem[i] = lcg();
        std::cout << large_mem[20000] << '\n';
    }
}

void remove_stdout()
{
    struct stat sb;

    if (fstat(STDOUT_FILENO, &sb) == -1)
    {
        std::perror("fstat");
        return;
    }

    if (!S_ISREG(sb.st_mode))
    {
        std::fprintf(stderr, "stdout is not a regular file\n");
        return;
    }

    char path[PATH_MAX];

#if defined(__APPLE__)
    if (fcntl(STDOUT_FILENO, F_GETPATH, path) == -1)
    {
        std::perror("fcntl F_GETPATH");
        return 0;
    }
#elif defined(__linux__)
    ssize_t len = readlink("/proc/self/fd/1", path, sizeof(path) - 1);
    if (len == -1)
    {
        perror("readlink");
        return;
    }
    path[len] = '\0';
#else
    static_assert("Unsupported OS", false);
#endif

    if (unlink(path) == -1)
    {
        perror("unlink");
        return;
    }
}
