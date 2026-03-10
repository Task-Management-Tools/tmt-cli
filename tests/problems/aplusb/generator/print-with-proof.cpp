#include "testlib.h"
#include <cassert>
#include <cstdio>
#include <fstream>
#include <iostream>

int main(int argc, char *argv[])
{
    if (argc < 3)
    {
        fprintf(stderr, "Arguments should not be empty.\n");
        return 1;
    }
    registerGen(argc, argv, 1);

    int a = opt<int>(1);
    int b = opt<int>(2);
    std::ofstream proof(argv[3]);
    std::cout << a << ' ' << b << '\n';
    proof << a << '+' << b << '=' << (long long)a + b << '\n';

    return 0;
}
