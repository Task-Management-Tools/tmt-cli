#include <iostream>
#include <string>

int main()
{
    std::string mode;
    std::cin >> mode;
    int t;
    std::cin >> t;
    for (int i = 0; i < t; i++)
    {
        std::string s;
        std::cin >> s;
        std::cout << s << '\n';
    }
}
