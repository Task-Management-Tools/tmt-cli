#include <iostream>

int main(int argc, char *argv[])
{
    if (argc < 2)
    {
        std::cerr << "Usage: " << argv[0] << " string\n";
        exit(-1);
    }
    std::cout << "I print " << argv[1] << ".\n";
}
