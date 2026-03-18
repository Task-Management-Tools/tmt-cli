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

std::string read_string()
{
    char buf[256] = {};
    if (std::scanf("%255[^ \n\r\t\v\f]", buf) != 1)
    {
        std::fputs("Failed to read string", stderr);
        std::abort();
    }

    return std::string(buf);
}

int read_char()
{
    int c = fgetc(stdin);
    return c;
}

int read_int()
{
    int c = std::fgetc(stdin);
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
    std::string strat = read_string();
    ensure(strat == "fixed" || strat == "adaptive");
    if (strat == "fixed")
    {
        ensure(read_char() == ' ');
        int n = read_int();
        ensure(1 <= n && n <= 1024);
    }
    ensure(read_char() == '\n');
    ensure(read_char() == EOF);
    exit(42);
}
