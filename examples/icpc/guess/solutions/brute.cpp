#include <iostream>
#include <cassert>

int main()
{
    for (int i = 1; i <= 1024; i++)
    {
        std::cerr << "guessing " << i << '\n';
        std::cout << i << std::endl;
        char c;
        std::cin >> c;
        if (c == '=')
            break;
    }
}