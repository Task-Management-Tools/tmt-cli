#include "testlib.h"

#include <iostream>
#include <string>

int main(int argc, char *argv[])
{
    registerGen(argc, argv, 1);
    std::ios::sync_with_stdio(0);

    int n = std::atoi(argv[1]);
    int w = std::atoi(argv[2]);

    std::cout << "first " << n << '\n';
    for (int i = 0; i < n; i++)
    {
        int actual_w = (w == -1 ? rnd.next(1, 20) : w);
        for (int j = 0; j < actual_w; j++)
            std::cout << rnd.next(0, 1);
        std::cout << '\n';
    }
}
