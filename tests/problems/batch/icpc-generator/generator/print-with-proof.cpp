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

    std::ofstream proof(argv[3]);
    std::cout << argv[1] << ' ' << argv[2] << '\n';
    proof << "the output limit is too short i cant write the full proof\n";

    return 0;
}
