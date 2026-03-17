#include "modulo.h"
#include <csignal>
#include <cstdlib>
#include <iostream>

using namespace std;

std::FILE* fin = stdin;
std::FILE* fout = stdout;

int main()
{
    std::signal(SIGPIPE, SIG_IGN);

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
