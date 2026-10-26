#include <math.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int lcg()
{
    static long long current = 1;
    int mul = 100, shift = 20, modulo = 998244353;
    return (current = ((long long)current * mul + shift) % modulo);
};

volatile double x = -1.0;
volatile double pi;

int main()
{
    {
        // check -lm
        pi = acos(x);
        // check stack
        char mem[32 * 1024 * 1024];
        for (int i = 0; i < sizeof(mem); i++)
            mem[i] = i % 256;
        fprintf(stderr, "%c", mem[sizeof(mem) - 1]);
    }

    char buf[256];
    if (scanf("%255s", buf) != 1)
        abort();

    if (strcmp(buf, "correct") == 0)
        puts("answer");
    if (strcmp(buf, "wrong") == 0)
        puts("not answer");
    if (strcmp(buf, "empty") == 0)
        puts("");
    // remove-stdout not implemented
    if (strcmp(buf, "timeout-cpu") == 0)
    {
        long long sum = 0;
        for (int i = 0; i < 1000000000; i++)
            sum += lcg();
        printf("%lld\n", sum);
    }
    if (strcmp(buf, "timeout-wall") == 0)
        usleep(1000000);
    if (strcmp(buf, "runerror-exit") == 0)
        return 1;
    if (strcmp(buf, "runerror-signal") == 0)
        raise(SIGABRT);
    if (strcmp(buf, "runerror-sigxfsz") == 0)
        raise(SIGXFSZ);
    if (strcmp(buf, "runerror-sigxcpu") == 0)
        raise(SIGXCPU);
    if (strcmp(buf, "runerror-any") == 0)
        abort();
    if (strcmp(buf, "memory-limit") == 0)
    {
        // 4096 * 256 bytes
        int *large_mem = (int *)malloc(256 * 1024 * 1024);
        for (int i = 0; i < 256 * 1024 * 1024 / sizeof(int); i += 1024)
            large_mem[i] = lcg();
        printf("%d\n", large_mem[20000]);
    }

    return 0;
}
