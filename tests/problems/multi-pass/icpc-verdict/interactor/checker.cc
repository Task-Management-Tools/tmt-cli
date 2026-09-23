#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>

constexpr int EXIT_AC = 42;
constexpr int EXIT_WA = 43;
constexpr int MAX_PASS = 3;

int main(int argc, char **argv)
{
    (void)argc;
    std::fstream input(argv[1]);
    std::fstream answer(argv[2]);

    auto phase_path = std::string(argv[3]) + "phase";
    int pass = 2;
    if (!std::filesystem::exists(phase_path))
        std::ofstream(phase_path) << pass;
    else
    {
        std::fstream phase_file(phase_path);
        phase_file >> pass;
        phase_file.seekg(std::ios_base::beg);
        phase_file << ++pass << '\n';
    }

    std::string action;
    std::cin >> action;
    if (action == "keep")
    {
        if (pass > MAX_PASS)
            return EXIT_WA;
        std::ofstream next_input(std::string(argv[3]) + "nextpass.in");
        next_input << pass;
        return EXIT_AC;
    }
    else if (action == "accept")
        return EXIT_AC;
    else
        return EXIT_WA;
}
