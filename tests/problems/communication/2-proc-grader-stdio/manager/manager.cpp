#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
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

FILE *mgr2sol[2] = {};
FILE *sol2mgr[2] = {};

int main(int argc, char **argv)
{
    std::signal(SIGPIPE, SIG_IGN);

    if (argc < 5)
        abort_with_reason("Invalid argument count");

    mgr2sol[0] = std::fopen(argv[2], "a");
    sol2mgr[0] = std::fopen(argv[1], "r");
    mgr2sol[1] = std::fopen(argv[4], "a");
    sol2mgr[1] = std::fopen(argv[3], "r");

    if (!mgr2sol[0])
        abort_with_reason("Cannot open mgr2sol 0");
    if (!sol2mgr[0])
        abort_with_reason("Cannot open sol2mgr 0");
    if (!mgr2sol[1])
        abort_with_reason("Cannot open mgr2sol 1");
    if (!sol2mgr[1])
        abort_with_reason("Cannot open sol2mgr 1");

    char input[16] = {};
    if (std::fscanf(stdin, "%15s", input) != 1)
        abort_with_reason("Cannot read input");
    if (input != "input"s)
        abort_with_reason("Input mismatch");

    std::mt19937 rd(0xABC);

    int inc_a = rd() % 256;
    int inc_b = rd() % 256;

    std::fprintf(mgr2sol[0], "%d\n", inc_a);
    std::fflush(mgr2sol[0]);
    std::fprintf(mgr2sol[1], "%d\n", inc_b);
    std::fflush(mgr2sol[1]);

    int ret_a, ret_b;
    if (std::fscanf(sol2mgr[0], "%d", &ret_a) != 1)
        wrong_with_reason("Cannot read participant 0 reply");
    if (std::fscanf(sol2mgr[1], "%d", &ret_b) != 1)
        wrong_with_reason("Cannot read participant 1 reply");
    if (ret_a != inc_a && ret_b != inc_b)
        wrong_with_reason("Participant reply wrong");

    std::fprintf(stdout, "%.6lf\n", 1.0);
    std::fflush(stdout);
    std::fprintf(stderr, "translate:success\n");
}
