#include <iostream>
#include <string>

int main()
{
    std::string mode;
    std::cin >> mode;
    int n;
    std::cin >> n;
    for (int i = 0; i < n; i++)
    {
        std::string s;
        std::cin >> s;
        std::cout << s << '\n';
    }
}
