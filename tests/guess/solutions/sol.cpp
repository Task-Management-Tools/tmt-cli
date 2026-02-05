#include <iostream>
#include <cassert>

int main()
{
    int l = 1, r = 1024;
    while (true)
    {
        int mid = (l + r) / 2;
        std::cerr << "guessing " << mid << '\n';
        std::cout << mid << std::endl;
        char c;
        std::cin >> c;
        if (c == '=')
            break;
        else if (c == '<')
            l = mid + 1;
        else if (c == '>')
            r = mid - 1;
        else 
            break; // guess exceeded
    }
}