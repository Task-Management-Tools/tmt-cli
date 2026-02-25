#include <fstream>
#include <iostream>
#include <string>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cassert>

const int EXIT_AC = 42;
const int EXIT_WA = 43;

static const int MAX_QUERIES = 11;

int main(int argc, char **argv)
{
    if (argc < 4)
    {
        std::cout << "Usage: %s judge_in judge_ans feedback_dir [options] < user_out";
        std::abort();
    }

    std::ifstream judgein(argv[1]);
    std::ifstream judgeans(argv[2]);
    std::ofstream judgemessage(std::string(argv[3]) + "judgemessage.txt");

    if (judgein.fail() || judgeans.fail() || judgemessage.fail())
        std::abort();

    auto wrong_answer = [&judgemessage](const char *err)
    {
        judgemessage << err << '\n';
        exit(EXIT_WA);
    };

    std::string mode;
    judgein >> mode;

    int queries = 0;
    if (mode == "fixed")
    {
        int answer;
        judgein >> answer;

        int guess;
        while (++queries <= MAX_QUERIES && std::cin >> guess)
        {
            if (guess == answer)
            {
                std::cout << "=" << std::endl;
                break;
            }
            else if (answer < guess)
                std::cout << "<" << std::endl;
            else
                std::cout << ">" << std::endl;
            std::cerr << "received guess " << guess << '\n';
        }
    }
    else if (mode == "adaptive")
    {
        int l = 1, r = 1024;
        int guess;
        while (++queries <= MAX_QUERIES && std::cin >> guess)
        {
            if (guess == l && guess == r)
            {
                std::cout << "=" << std::endl;
                break;
            }
            else if (l > guess)
                std::cout << ">" << std::endl;
            else if (r < guess)
                std::cout << "<" << std::endl;
            else
            {
                int small = guess - l, large = r - guess;
                if (small < large)
                    l = guess + 1;
                else
                    r = guess - 1;
                if (l > guess)
                    std::cout << ">" << std::endl;
                else if (r < guess)
                    std::cout << "<" << std::endl;
                else
                    std::abort(); // should be impossible
            }
        }
    }
    else
        std::abort(); // should be impossible

    if (queries > MAX_QUERIES)
    {
        std::cout << "-" << std::endl;
        wrong_answer(("Participant exceeded maximum queries count " + std::to_string(MAX_QUERIES)).c_str());
    }
    if (std::cin.fail())
        wrong_answer("Failed to read integer from the participant");

    exit(EXIT_AC);
}
