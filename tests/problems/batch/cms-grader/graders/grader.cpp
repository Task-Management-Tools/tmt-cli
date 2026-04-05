#include "gradertest.h"
#include <cstdlib>
#include <iostream>
#include <string>

namespace
{
    bool called_graderfunc = false;
}

void graderfunc()
{
    ::called_graderfunc = true;
}

int main()
{
    std::string str;
    std::cin >> str;

    if (str != "input")
        std::abort();

    userfunc();

    if (called_graderfunc)
        std::cout << "called graderfunc\n";
}
