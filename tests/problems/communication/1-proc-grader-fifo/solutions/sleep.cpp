#include "modulo.h"

#include <chrono>
#include <thread>

using namespace std::chrono_literals;

int modulo2(int n)
{
    (void)n;
    std::this_thread::sleep_for(0.1s);
    return n % 2;
}
