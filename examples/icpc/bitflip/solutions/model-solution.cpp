#include <algorithm>
#include <iostream>
#include <string>

int main()
{
    std::string mode;
    std::cin >> mode;
    int n;
    std::cin >> n;

    if (mode == "first")
    {
        for (int i = 0; i < n; i++)
        {
            std::string s;
            std::cin >> s;
            std::cout << s << '0' << '\n';
        }
    }
    else
    {
        for (int i = 0; i < n; i++)
        {
            std::string s;
            std::cin >> s;
            for (auto &c : s)
                c ^= (s.back() == '1');
            s.pop_back();
            std::cout << s << '\n';
        }
    }
}
