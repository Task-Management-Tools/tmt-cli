#include "modulo.h"
#include <csignal>
#include <cstdio>
#include <cstdlib>

using namespace std;

std::FILE* fin = nullptr;
std::FILE* fout = nullptr;

int main(int argc, char **argv)
{
    std::signal(SIGPIPE, SIG_IGN);

    if (argc < 3)
        std::abort();

    fin = std::fopen(argv[1], "r");
    fout = std::fopen(argv[2], "w");

    if (!fin || !fout)
        std::abort();

    while (true)
    {
        int n = -1;
        if (std::fscanf(fin, "%d", &n) != 1)
            std::abort();

        if (n == -1)
            break;
        std::fprintf(fout, "%d\n", modulo2(n));
        std::fflush(fout);
    }
    return 0;
}
