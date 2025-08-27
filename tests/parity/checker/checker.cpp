#include <stdexcept>
#include <iostream>
#include <fstream>
#include <string>
#include <regex>

const int EXIT_AC = 42;
const int EXIT_WA = 43;
const char USAGE[] = "Usage: %s judge_in judge_ans feedback_file [options] < user_out";

int main(int argc, char **argv)
{
    if (argc < 4)
        throw std::runtime_error(USAGE);

    using namespace std::string_literals;

    // this direct concatenate is guaranteed by the ICPC package format standard
    std::ofstream feedback(argv[3] + "judgemessage.txt"s);
    std::ifstream testcase_input(argv[1]);
    std::ifstream testcase_answer(argv[2]);

    std::smatch _;
    const std::regex numbers("0|-?[1-9][0-9]*");

    std::string input, answer, output;
    testcase_input >> input;
    if (!(testcase_answer >> answer) || !std::regex_match(answer, _, numbers))
    {
        feedback << "judge has no output or is not a number" << std::endl;
        abort();
    }
    if (!(std::cin >> output) || !std::regex_match(answer, _, numbers))
    {
        feedback << "contestant has no output or is not a number" << std::endl;
        exit(EXIT_WA);
    }

    if ((answer.back() ^ input.back()) % 2 != 0)
    {
        feedback << "judge's answer isn't correct" << std::endl;
        feedback.flush();
        std::abort();
    }
    if ((output.back() ^ input.back()) % 2 != 0)
    {
        feedback << "contestant's answer isn't correct" << std::endl;
        feedback.flush();
        exit(EXIT_WA);
    }

    exit(EXIT_AC);
}