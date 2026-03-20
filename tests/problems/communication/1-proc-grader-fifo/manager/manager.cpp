#include <csignal>
#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <string>

using namespace std::string_literals;

[[noreturn]] inline void abort_with_reason(const char *reason)
{
    std::fprintf(stderr, "%s\n", reason);
    std::abort();
}
[[noreturn]] inline void wrong_with_reason(const char *reason)
{
    std::fprintf(stdout, "%.6lf\n", 0.0);
    std::fflush(stdout);
    std::fprintf(stderr, "translate:wrong\n%s\n", reason);
    std::exit(0);
}

int main(int argc, char **argv)
{
    std::signal(SIGPIPE, SIG_IGN);

    if (argc < 3)
        abort_with_reason("Invalid argument count");

    FILE *mgr2sol = std::fopen(argv[2], "a");
    FILE *sol2mgr = std::fopen(argv[1], "r");

    if (!mgr2sol)
        abort_with_reason("Cannot open mgr2sol");
    if (!sol2mgr)
        abort_with_reason("Cannot open sol2mgr");

    char input[16] = {};
    if (std::fscanf(stdin, "%15s", input) != 1)
        abort_with_reason("Cannot read input");
    if (input != "input"s)
        abort_with_reason("Input mismatch");

    for (int i = 0; i < 256; i++)
    {
        std::fprintf(mgr2sol, "%d\n", i);
        std::fflush(mgr2sol);

        int ret = -1;
        if (std::fscanf(sol2mgr, "%d", &ret) != 1)
            wrong_with_reason("Cannot read participant reply");
        if (ret != i % 2)
            wrong_with_reason("Participant reply wrong");
    }
    std::fprintf(mgr2sol, "-1\n");
    std::fflush(mgr2sol);

    std::fprintf(stdout, "%.6lf\n", 1.0);
    std::fflush(stdout);
    std::fprintf(stderr, "translate:success\n");
}
