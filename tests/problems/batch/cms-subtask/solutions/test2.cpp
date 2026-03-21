#include <chrono>
#include <cstdlib>
#include <iostream>
#include <map>
#include <string>
#include <thread>
#include <utility>

using namespace std::chrono_literals;

void correct(int) { std::cout << 1.0 << '\n'; }
void wrong(int) { std::cout << 0.0 << '\n'; }
void partial(int index)
{
    std::cout << 0.4 + 0.3 * index << '\n';
}
void timeout_a_bit(int index)
{
    auto prev = std::chrono::steady_clock::now();
    while (std::chrono::steady_clock::now() - prev <= 505ms);
}
void timeout(int index)
{
    auto prev = std::chrono::steady_clock::now();
    while (std::chrono::steady_clock::now() - prev <= 1s);
}
void memory(int index)
{
    auto ptr = static_cast<int *>(std::malloc(128 * 1024 * 1024));
    for (int j = 0; j < 128 * 1024 * 1024 / sizeof(int); j += 1024)
        ptr[j] = 0;
    std::cerr << ptr[123] << '\n';
}
[[noreturn]] void runtime_error(int)
{
    std::abort();
}

int main()
{
    std::map<std::pair<std::string, int>, void (*)(int)> mapping;

    mapping[std::pair("sample", 0)] = correct;
    mapping[std::pair("subtask1", 0)] = correct;
    mapping[std::pair("subtask1", 1)] = correct;
    mapping[std::pair("subtask2", 0)] = correct;
    mapping[std::pair("subtask2", 1)] = correct;
    mapping[std::pair("subtask2", 2)] = partial;
    mapping[std::pair("subtask3", 0)] = correct;
    mapping[std::pair("subtask3", 1)] = timeout_a_bit;
    mapping[std::pair("subtask4", 0)] = correct;
    mapping[std::pair("full", 0)] = correct;
    mapping[std::pair("full", 1)] = partial;

    std::string input;
    int index;
    std::cin >> input >> index;

    auto prev = std::chrono::steady_clock::now();
    while (std::chrono::steady_clock::now() - prev <= 100ms + 50ms * index)
        ;
    for (int i = 0; i < index; i++)
    {
        auto ptr = static_cast<int *>(std::malloc(32 * 1024 * 1024));
        for (int j = 0; j < 32 * 1024 * 1024 / sizeof(int); j += 1024)
            ptr[j] = 0;
        std::cerr << ptr[123] << '\n';
        // intentional leak
    }

    mapping[std::pair(input, index)](index);
}
