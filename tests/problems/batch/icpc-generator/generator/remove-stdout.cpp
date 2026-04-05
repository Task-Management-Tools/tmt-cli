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

int main()
{
    struct stat sb;

    if (fstat(STDOUT_FILENO, &sb) == -1)
    {
        perror("fstat");
        return 0;
    }

    if (!S_ISREG(sb.st_mode))
    {
        std::cerr << "stdout is not a regular file.\n";
        return 0;
    }

    char path[PATH_MAX];

#if defined(__APPLE__)
    if (fcntl(STDOUT_FILENO, F_GETPATH, path) == -1)
    {
        perror("fcntl F_GETPATH");
        return 0;
    }
#elif defined(__linux__)
    ssize_t len = readlink("/proc/self/fd/1", path, sizeof(path) - 1);
    if (len == -1)
    {
        perror("readlink");
        return 0;
    }
    path[len] = '\0';
#else
    static_assert("Unsupported OS", false);
#endif

    if (unlink(path) == -1)
    {
        perror("unlink");
        return 0;
    }
}
