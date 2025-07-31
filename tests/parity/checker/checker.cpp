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

    std::string answer, output;
    if (!(testcase_answer >> answer) || !std::regex_match(answer, _, numbers))
    {
        feedback << argv[3] << ": judge has no output or is not a number\n";
        feedback.flush();
        abort();
    }
    if (!(std::cin >> output) || !std::regex_match(answer, _, numbers))
    {
        feedback << argv[3] << ": contestant has no output or is not a number\n";
        feedback.flush();
        exit(EXIT_WA);
    }
    // special string to check checker crash
    feedback << output;

    if (output == "1234567890")
        abort();
    // ... and timeout:
    if (output == "1234567891")
        for (;;)
            ;

    if ((answer.back() ^ output.back()) % 2 != 0)
    {
        feedback << argv[3] << ": output mismatch\n";
        feedback.flush();
        exit(EXIT_WA);
    }

    exit(EXIT_AC);
}