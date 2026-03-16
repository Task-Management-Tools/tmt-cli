#include "modulo.h"
#include <csignal>
#include <cstdlib>
#include <iostream>

using namespace std;

int main()
{
    std::signal(SIGPIPE, SIG_IGN);

    while (true)
    {
        int n;
        if (!(std::cin >> n))
            std::abort();

        if (n == -1)
            break;
        std::cout << modulo2(n) << std::endl;
    }
    return 0;
}
