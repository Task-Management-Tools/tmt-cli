#include <chrono>
#include <thread>
#include <iostream>
using namespace std::chrono_literals;

int main()
{
    std::this_thread::sleep_for(200ms);
    std::cout << "answer\n";
}
