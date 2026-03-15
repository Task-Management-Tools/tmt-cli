#include <cstdio>
#include <cstdlib>

int main(int argc, char **argv)
{
    if (argc == 1)
        std::exit(EXIT_FAILURE);
    for (int i = 1; i < argc; i++)
        std::fprintf(stdout, "%s\n", argv[i]);
}
