#include "guess.h"

int find_number(int n)
{
    for (int i = n - 1; i >= 0; i--)
        if (!is_less_than(i))
            return i;
    return 0;
}
