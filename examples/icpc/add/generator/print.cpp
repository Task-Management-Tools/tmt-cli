#include "testlib.h"
#include <cstdio>
#include <cassert>
#include <iostream>

int main(int argc, char* argv[]) {
    if (argc < 2) return std::cerr << "Arguments should not be empty.\n", 1;
    registerGen(argc, argv, 1);

    int a = opt<int>(1);
    int b = opt<int>(2);
    printf("%d %d\n", a, b);

    return 0;
}
