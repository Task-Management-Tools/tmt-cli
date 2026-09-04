#include <iostream>
#include <string>

char buf[96 * 1024 * 1024];

int main()
{
    for (int i = 0; i < sizeof(buf); i++)
        buf[i] = i % 256;
    std::cout << "answer\n";
}
