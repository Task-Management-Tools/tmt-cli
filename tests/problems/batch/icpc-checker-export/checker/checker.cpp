#include "header.h"

constexpr int EXIT_AC = 42;
constexpr int EXIT_WA = 43;

int main()
{
    std::string output;
    std::cin >> output;

    return output.size() == 6 ? EXIT_AC : EXIT_WA;
}
