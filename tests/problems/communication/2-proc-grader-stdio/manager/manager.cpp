#include <csignal>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <random>

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

    if (argc < 5)
        abort_with_reason("Invalid argument count");

    std::ofstream mgr2sol_0(argv[2]);
    std::ifstream sol2mgr_0(argv[1]);
    std::ofstream mgr2sol_1(argv[4]);
    std::ifstream sol2mgr_1(argv[3]);

    if (!mgr2sol_0)
        abort_with_reason("Cannot open mgr2sol 0");
    if (!sol2mgr_0)
        abort_with_reason("Cannot open sol2mgr 0");
    if (!mgr2sol_1)
        abort_with_reason("Cannot open mgr2sol 1");
    if (!sol2mgr_1)
        abort_with_reason("Cannot open sol2mgr 1");

    std::string input;
    if (!(std::cin >> input))
        abort_with_reason("Cannot read input");
    if (input != "input")
        abort_with_reason("Input mismatch");

    std::mt19937 rd(0xABC);

    int cnt_a = 0;
    int cnt_b = 0;
    for (int i = 0; i < 256; i++)
    {
        int inc_a = rd() % 256;
        int inc_b = rd() % 256;

        mgr2sol_0 << inc_a << std::endl;
        mgr2sol_1 << inc_b << std::endl;

        int ret_a, ret_b;
        if (!(sol2mgr_0 >> ret_a))
            wrong_with_reason("Cannot read participant 0 reply");
        if (!(sol2mgr_1 >> ret_b))
            wrong_with_reason("Cannot read participant 1 reply");
        if (ret_a != (cnt_a += inc_a) && ret_b != (cnt_b += inc_b))
            wrong_with_reason("Participant reply wrong");
    }
    mgr2sol_0 << -1 << std::endl;
    mgr2sol_1 << -1 << std::endl;

    std::cout << 1.0 << std::endl;
    std::cout << "translate:correct" << std::endl;
}
