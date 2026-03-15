#include "guess.h"

#include <thread>
#include <chrono>

using namespace std::chrono_literals;

int find_number(int n)
{
    std::this_thread::sleep_for(1min);
    return 0;
}
