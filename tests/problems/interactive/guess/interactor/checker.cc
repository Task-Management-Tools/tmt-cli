// not adaptive, make it simple
#include <fstream>
#include <iostream>
#include <cstdlib>

constexpr int EXIT_AC = 42;
constexpr int EXIT_WA = 43;
constexpr int MAX_QUERIES = 11;

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

    int queries = 0;
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

    if (queries > MAX_QUERIES)
    {
        std::cout << "-" << std::endl;
        judgemessage << "Participant exceeded maximum queries count " << MAX_QUERIES << '\n';
        return EXIT_WA;
    }
    if (std::cin.fail())
    {
        judgemessage << "Failed to read integer from the participant";
        return EXIT_WA;
    }
    return EXIT_AC;
}
