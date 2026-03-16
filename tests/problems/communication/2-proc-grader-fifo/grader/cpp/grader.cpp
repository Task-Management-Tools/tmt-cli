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

    if (argc < 4)
        std::abort();

    std::ifstream fin(argv[1]);
    std::ofstream fout(argv[2]);

    if (!fin || !fout)
        std::abort();

    int id = -1;
    {
        const char *begin = argv[3];
        const char *end = argv[3] + std::strlen(argv[3]);
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
        int n = -1;
        if (!(fin >> n))
            std::abort();

        if (n == -1)
            break;

        int upd = (id == 0 ? accumulateA(n) : accumulateB(n));
        fout << upd << std::endl;
    }
    return 0;
}
