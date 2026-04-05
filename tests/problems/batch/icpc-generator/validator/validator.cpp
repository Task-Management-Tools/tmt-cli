#include <cstdlib>
#include <iostream>

int main()
{
    long long a, b;
    if (!(std::cin >> a >> b))
        std::exit(EXIT_FAILURE);
    while (std::cin.peek() != decltype(std::cin)::traits_type::eof())
        if (!std::isspace(std::cin.get()))
            std::exit(EXIT_FAILURE);

    std::exit(42); // for icpc
}
