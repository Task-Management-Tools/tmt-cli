#include "accumulate.h"
#include <charconv>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <cstring>

using namespace std;

std::FILE *fin = stdin;
std::FILE *fout = stdout;

int main(int argc, char **argv)
{
    std::signal(SIGPIPE, SIG_IGN);

    if (argc < 2)
        std::abort();

    if (!fin || !fout)
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

    int n;
    if (std::fscanf(fin, "%d", &n) != 1)
        std::abort();

    int upd = (id == 0 ? accumulateA(n) : accumulateB(n));
    std::fprintf(fout, "%d\n", upd);
    std::fflush(fout);

    return 0;
}
