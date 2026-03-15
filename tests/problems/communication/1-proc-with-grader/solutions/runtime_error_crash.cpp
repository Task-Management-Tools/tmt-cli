#include "guess.h"

#include <csignal>

int find_number(int n)
{
    std::raise(SIGQUIT);
    return 0;
}
