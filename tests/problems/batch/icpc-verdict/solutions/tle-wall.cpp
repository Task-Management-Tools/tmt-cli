#include <chrono>
#include <thread>
#include <iostream>
using namespace std::chrono_literals;

int main()
{
    // DOMjudge add 1 second for wall clock
    std::this_thread::sleep_for(1550ms);
    std::cout << "answer\n";
}
