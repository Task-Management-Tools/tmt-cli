#include <cstdio>
#include <algorithm>

using namespace std;

int main()
{
    long long a, b;
    while (~scanf("%lld %lld", &a, &b))
        printf("%lld\n", abs(a - b));
}
