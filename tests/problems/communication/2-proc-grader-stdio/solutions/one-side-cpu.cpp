#include "accumulate.h"

#include <chrono>
#include <thread>

using namespace std::chrono_literals;

namespace
{
    int shared_cnt = 0;
}

int accumulateA(int n) { return shared_cnt += n; }
int accumulateB(int n)
{
    auto prev = std::chrono::steady_clock::now();
    while (std::chrono::steady_clock::now() - prev <= 150ms);
    return shared_cnt += n;
}
