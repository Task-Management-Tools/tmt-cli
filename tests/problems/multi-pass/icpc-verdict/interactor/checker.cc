#include <cassert>
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
    std::ifstream input(argv[1]);
    std::ifstream answer(argv[2]);

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

    // assert the input is properly updated
    int input_pass = -1;
    input >> input_pass;
    std::cerr << "expected next pass: " << pass << "; read input pass: " << input_pass << '\n';
    assert(input_pass == pass - 1);

    std::string action;
    std::cin >> action;
    if (action == "keep")
    {
        if (pass > MAX_PASS)
            return EXIT_WA;
        std::ofstream next_input(std::string(argv[3]) + "nextpass.in");
        next_input << pass << '\n';
        return EXIT_AC;
    }
    else if (action == "accept")
        return EXIT_AC;
    else
        return EXIT_WA;
}
