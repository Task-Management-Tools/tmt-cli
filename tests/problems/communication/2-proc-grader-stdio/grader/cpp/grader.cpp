#include "accumulate.h"
#include <charconv>
#include <csignal>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>

using namespace std;

int main(int argc, char **argv)
{
    std::signal(SIGPIPE, SIG_IGN);

    if (argc < 2)
        std::abort();

    int id = -1;
    {
        const char *begin = argv[1];
        const char *end = argv[1] + std::strlen(argv[1]);
        auto [ptr, ec] = std::from_chars(begin, end, id);
        if (ec != std::errc())
            std::abort();
        if (ptr != end)
            std::abort();
        if (id != 0 && id != 1)
            std::abort();
    }

    while (true)
    {
        int n;
        if (!(std::cin >> n))
            std::abort();

        if (n == -1)
            break;

        int upd = (id == 0 ? accumulateA(n) : accumulateB(n));
        std::cout << upd << std::endl;
    }
    return 0;
}
