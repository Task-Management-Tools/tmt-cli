#include <chrono>
#include <iostream>
using namespace std::chrono_literals;

int main()
{
    auto now = std::chrono::steady_clock::now();
    while (std::chrono::steady_clock::now() - now <= 200ms);
    std::cout << "answer\n";
}
