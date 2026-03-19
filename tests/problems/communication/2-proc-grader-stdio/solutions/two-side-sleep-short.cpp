#include "accumulate.h"

#include <chrono>
#include <thread>

using namespace std::chrono_literals;

namespace
{
    int shared_cnt = 0;
}

int accumulateA(int n)
{
    std::this_thread::sleep_for(150ms);
    return shared_cnt += n;
}

int accumulateB(int n)
{
    std::this_thread::sleep_for(150ms);
    return shared_cnt += n;
}
