#include <cstdio>

int main(int argc, char *argv[])
{
    for (int i = 1; i < argc; i++)
        std::printf("%s%c", argv[i], " \n"[i + 1 == argc]);
    return 0;
}
