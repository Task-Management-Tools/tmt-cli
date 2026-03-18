#include <cstdlib>
#include <iostream>
#include <thread>
#include <chrono>

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

using namespace std::chrono_literals;

#include <filesystem>
#include <fstream>
#include <iostream>

std::ifstream open_proof()
{
    // current workaround
    for (const auto &entry : std::filesystem::directory_iterator("."))
        if (entry.path().extension() == ".proof")
        {
            std::ifstream file(entry.path());
            return file;
        }

    std::abort();
}

void remove_stdin()
{
    struct stat sb;

    if (fstat(STDIN_FILENO, &sb) == -1)
    {
        std::perror("fstat");
        return;
    }

    if (!S_ISREG(sb.st_mode))
    {
        std::fprintf(stderr, "stdin is not a regular file\n");
        return;
    }

    char path[PATH_MAX];

#if defined(__APPLE__)
    if (fcntl(STDIN_FILENO, F_GETPATH, path) == -1)
    {
        std::perror("fcntl F_GETPATH");
        return 0;
    }
#elif defined(__linux__)
    ssize_t len = readlink("/proc/self/fd/0", path, sizeof(path) - 1);
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

int main()
{
    std::string input;
    std::cin >> input;

    if (input == "valid")
        std::exit(42);
    if (input == "invalid")
        std::exit(EXIT_FAILURE);
    if (input == "crash")
        std::abort();
    if (input == "timeout")
        std::this_thread::sleep_for(10.1s);
    if (input == "remove")
        remove_stdin();
    if (input == "proof")
    {
        auto stream = open_proof();
        std::string proof;
        stream >> proof;
        if (proof != "waterproof")
            std::abort();
    }
    std::exit(42); // for icpc
}
