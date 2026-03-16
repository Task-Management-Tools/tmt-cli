#include "modulo.h"
#include <csignal>
#include <fstream>

using namespace std;

int main(int argc, char **argv)
{
    std::signal(SIGPIPE, SIG_IGN);

    if (argc < 3)
        std::abort();

    std::ifstream fin(argv[1]);
    std::ofstream fout(argv[2]);

    if (!fin || !fout)
        std::abort();

    while (true)
    {
        int n = -1;
        if (!(fin >> n))
            std::abort();

        if (n == -1)
            break;
        fout << modulo2(n) << std::endl;
    }
    return 0;
}
