#include <cstdio>
#include <cstdlib>
#include <string>

#define ensure(...)                                                \
    do                                                             \
    {                                                              \
        if (!(__VA_ARGS__))                                        \
        {                                                          \
            std::fputs("Condition failed: " #__VA_ARGS__, stderr); \
            std::abort();                                          \
        }                                                          \
    } while (false);

int read_char()
{
    return fgetc(stdin);
}

int read_int()
{
    int c = read_char();
    if (!std::isdigit(c))
    {
        std::fputs("Expecting a digit", stderr);
        std::abort();
    }
    std::ungetc(c, stdin);
    int i;
    if (std::scanf("%d", &i) != 1)
    {
        std::fputs("Failed to read int", stderr);
        std::abort();
    }
    return i;
}

int main()
{
    int n = read_int();
    ensure(1 <= n && n <= 1024);
    ensure(read_char() == '\n');
    ensure(read_char() == EOF);
    return 42;
}
