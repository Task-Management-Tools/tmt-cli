#include <algorithm>
#include <filesystem>
#include <fstream>
#include <format>
#include <iostream>
#include <random>
#include <string>
#include <vector>

const int EXIT_AC = 42;
const int EXIT_WA = 43;

int main(int argc, char **argv)
{
    (void)argc;
    std::ifstream input(argv[1]);
    std::ifstream answer(argv[2]);
    std::ofstream feedback(std::string(argv[3]) + "judgemessage.txt", std::ios::app);

    auto wrong_answer = [&feedback](std::string err)
    {
        feedback << err << std::endl;
        exit(EXIT_WA);
    };

    // Note: regardless of pass, the input still contains the original input.
    // If the interactor need the produced input, they must save it independently.
    int n;
    input.ignore(6); // "first"
    input >> n;

    std::vector<std::string> original(n);
    for (int i = 0; i < n; i++)
        input >> original[i];

    // All non-special files in the judge feedback directory preserves across check.
    // Thus, we can use this file to keep track of the number of passes
    std::filesystem::path marker = std::filesystem::path(argv[3]) / "pass-marker";
    // Pass 1
    if (!std::filesystem::exists(marker))
    {
        {
            std::ofstream of(marker);
            of << "!";
        }

        std::vector<std::string> modified(n);
        for (int i = 0; i < n; i++)
        {
            if (!(std::cin >> modified[i]))
                wrong_answer(std::format("cannot read {}-th output string from contestant", i + 1));

            for (auto c : modified[i])
                if (c != '0' && c != '1')
                    wrong_answer(std::format("{}-th output string from contestant is not a bit-string", i + 1));

            // Fine because modified[i].size() >= 1
            if (original[i] != modified[i]
                && original[i] != modified[i].substr(1)
                && original[i] != modified[i].substr(0, modified[i].size() - 1))
                wrong_answer(std::format("{}-th output string from contestant is illegal", i + 1));
        }

        // Hash the input for deterministic random seed
        // Alternatively, include the seed in the answer file
        unsigned long long seed = 0;
        constexpr unsigned long long base = 0x5851F42D4C957F2D;
        for (int i = 0; i < n; i++)
            seed = seed * base + std::stoull(original[i], nullptr, 2);
        std::mt19937_64 rd(seed);

        std::ofstream next_input(std::string(argv[3]) + "nextpass.in");
        next_input << "second " << n << '\n';
        for (const auto &str : modified)
        {
            std::string out = str;
            if (rd() % 2 == 0)
                std::transform(out.begin(), out.end(), out.begin(), [](char c) { return c ^ 1; });
            next_input << out << '\n';
        }
        next_input.close();
    }
    // Pass 2
    else
    {
        for (int i = 0; i < n; i++)
        {
            std::string recovered;
            if (!(std::cin >> recovered))
                wrong_answer(std::format("cannot read {}-th output string from contestant", i + 1));
            if (original[i] != recovered)
                wrong_answer(std::format("the {}-th input string is not successfully recovered", i + 1));
        }
    }
    return EXIT_AC;
}
