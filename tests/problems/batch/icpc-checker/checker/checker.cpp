#include <chrono>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <thread>

const int EXIT_AC = 42;
const int EXIT_WA = 43;

using namespace std::chrono_literals;

int main(int argc, char **argv)
{
    if (argc < 4)
        throw std::runtime_error("Invalid usage");

    using namespace std::string_literals;

    // this direct concatenate is guaranteed by the ICPC package format standard
    std::ofstream feedback(argv[3] + "judgemessage.txt"s);
    std::ifstream testcase_input(argv[1]);
    std::ifstream testcase_answer(argv[2]);

    std::string input, answer, output;
    testcase_input >> input;
    std::cin >> output;
    testcase_answer >> answer;

    if (input != "input")
        throw std::runtime_error("Input mismatch");
    if (answer != "answer")
        throw std::runtime_error("Answer mismatch");

    if (output == "answer")
    {
        feedback << "correct feedback" << std::endl;
        exit(EXIT_AC);
    }
    if (output == "wrong")
    {
        feedback << "wrong feedback" << std::endl;
        exit(EXIT_WA);
    }
    if (output == "crash")
        throw std::runtime_error("Intentional crash");
    if (output == "timeout")
        std::this_thread::sleep_for(10.1s);

    throw std::runtime_error("Unreachable code");
}
