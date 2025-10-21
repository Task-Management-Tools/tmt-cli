#include <cstdio>

int main(int argc, char **argv)
{
    if (argc == 2)
        fprintf(stdout, "%s\n", argv[1]);
    else
        fprintf(stdout, "%s %s\n", argv[1], argv[2]);
}