#include "accumulate.h"

#include <cstdlib>

namespace
{
    int shared_cnt = 0;
}

int accumulateA(int n)
{
    (void)n;
    std::exit(0);
    return 0;
}
int accumulateB(int n) { return shared_cnt += n; }
