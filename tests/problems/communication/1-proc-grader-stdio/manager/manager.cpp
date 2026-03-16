#include <csignal>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>

[[noreturn]] inline void abort_with_reason(const char *reason)
{
    std::cerr << reason << std::endl;
    std::abort();
}
[[noreturn]] inline void wrong_with_reason(const char *reason)
{
    std::cout << 0.0 << std::endl;
    std::cerr << "translate:wrong" << std::endl
              << reason << std::endl;
    std::abort();
}

int main(int argc, char **argv)
{
    std::signal(SIGPIPE, SIG_IGN);

    if (argc < 3)
        abort_with_reason("Invalid argument count");

    std::ofstream mgr2sol(argv[2]);
    std::ifstream sol2mgr(argv[1]);

    if (!mgr2sol)
        abort_with_reason("Cannot open mgr2sol");
    if (!sol2mgr)
        abort_with_reason("Cannot open sol2mgr");

    std::string input;
    if (!(std::cin >> input))
        abort_with_reason("Cannot read input");
    if (input != "input")
        abort_with_reason("Input mismatch");

    for (int i = 0; i < 256; i++)
    {
        mgr2sol << i << std::endl;

        int ret;
        if (!(sol2mgr >> ret))
            wrong_with_reason("Cannot read participant reply");
        if (ret != i % 2)
            wrong_with_reason("Participant reply wrong");
    }
    mgr2sol << -1 << std::endl;

    std::cout << 1.0 << std::endl;
    std::cout << "translate:correct" << std::endl;
}
