#include "accumulate.h"

namespace
{
    // should be independent due to process separation
    int shared_cnt = 0;
}

int accumulateA(int n) { return shared_cnt += n; }
int accumulateB(int n) { return shared_cnt += n; }
