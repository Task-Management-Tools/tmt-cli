#include "guess.h"

int find_number(int n)
{
    int l = 0, r = n - 1;
    while (l < r)
    {
        int mid = (l + r + 1) / 2;
        if (is_less_than(mid))
            r = mid - 1;
        else
            l = mid;
    }
    return l;
}
