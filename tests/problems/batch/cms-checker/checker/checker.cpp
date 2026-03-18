#include <chrono>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <string>
#include <thread>

using namespace std::chrono_literals;

int main(int argc, char **argv)
{
    if (argc < 4)
        std::abort();

    std::ifstream testcase_input(argv[1]);
    std::ifstream testcase_answer(argv[2]);
    std::ifstream testcase_output(argv[3]);

    using namespace std::string_literals;

    std::string input, answer, output;
    testcase_input >> input;
    testcase_output >> output;
    testcase_answer >> answer;

    if (input != "input")
        throw std::runtime_error("Input mismatch");
    if (answer != "answer")
        throw std::runtime_error("Answer mismatch");

    if (output == "answer")
    {
        std::cout << "1.0" << std::endl;
        std::cerr << "correct feedback" << std::endl;
        std::cerr << "correct reason" << std::endl;
    }
    if (output == "wrong")
    {
        std::cout << "0.0" << std::endl;
        std::cerr << "wrong feedback" << std::endl;
        std::cerr << "wrong reason" << std::endl;
    }
    if (output == "partial")
    {
        std::cout << "0.5" << std::endl;
        std::cerr << "partial feedback" << std::endl;
        std::cerr << "partial reason" << std::endl;
    }
    if (output == "crash")
        std::exit(1);
    if (output == "signal")
        std::abort();
    if (output == "timeout")
        std::this_thread::sleep_for(10.1s);
    if (output == "fail")
        std::exit(0); // do nothing so I fails
}
