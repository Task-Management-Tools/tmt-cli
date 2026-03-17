#include "accumulate.h"
#include <charconv>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <cstring>

using namespace std;

std::FILE* fin = nullptr;
std::FILE* fout = nullptr;

int main(int argc, char **argv)
{
    std::signal(SIGPIPE, SIG_IGN);

    if (argc < 4)
        std::abort();

    fin = std::fopen(argv[1], "r");
    fout = std::fopen(argv[2], "w");

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
        if (std::fscanf(fin, "%d", &n) != 1)
            std::abort();

        if (n == -1)
            break;

        int upd = (id == 0 ? accumulateA(n) : accumulateB(n));
        std::fprintf(fout, "%d\n", upd);
        std::fflush(fout);
    }
    return 0;
}
