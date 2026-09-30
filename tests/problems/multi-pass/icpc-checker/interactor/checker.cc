#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>

const int EXIT_AC = 42;
const int EXIT_WA = 43;

void check_and_tamper_input(std::fstream &fs)
{
    static const char bad_marker[] = "bad";
    std::string s;
    fs >> s;
    std::cerr << "get " << s << '\n';
    if (s == bad_marker)
    {
        std::cerr << "input stream is not properly copied\n";
        std::abort();
    }
    fs.seekp(0, std::ios_base::beg);
    fs << bad_marker;
}

int main(int argc, char **argv)
{
    (void)argc;
    std::fstream input(argv[1]);
    std::fstream answer(argv[2]);

    check_and_tamper_input(input);
    check_and_tamper_input(answer);

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
    while (std::cin >> action)
        if (action == "keep")
        {
            std::ofstream next_input(std::string(argv[3]) + "nextpass.in");
            next_input << pass;
        }
        else if (action == "accept")
            return EXIT_AC;
        else if (action == "reject")
            return EXIT_WA;
    std::abort();
}
