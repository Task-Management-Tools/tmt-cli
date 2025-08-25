#include <fstream>
#include <iostream>
#include <string>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cassert>

const int EXIT_AC = 42;
const int EXIT_WA = 43;

FILE *judgemessage = NULL;

void wrong_answer(const char *err)
{
	fprintf(judgemessage, "%s\n", err);
	exit(EXIT_WA);
}

FILE *openfeedback(const char *feedbackdir, const char *feedback, const char *whoami)
{
	std::string path = std::string(feedbackdir) + "/" + std::string(feedback);
	FILE *res = fopen(path.c_str(), "w");
	if (!res)
		std::abort();
	return res;
}

const char *USAGE = "Usage: %s judge_in judge_ans feedback_file [options] < user_out";

int main(int argc, char **argv)
{
	if (argc < 4)
		std::abort();

	judgemessage = openfeedback(argv[3], "judgemessage.txt", argv[0]);

	std::ifstream judgein(argv[1]), judgeans(argv[2]);
	if (judgein.fail() || judgeans.fail())
		std::abort();

	std::string mode;
	judgein >> mode;

	if (mode == "fixed")
	{
		int answer;
		judgein >> answer;

		int guess;
		while (std::cin >> guess)
		{
			if (guess == answer)
			{
				std::cout << "=" << std::endl;
				break;
			}
			else if (guess < answer)
				std::cout << "<" << std::endl;
			else
				std::cout << ">" << std::endl;
			std::cerr << "received guess " << guess << '\n';
		}
		if (std::cin.fail())
			wrong_answer("Failed to read interger from the participant");
	}
	else if (mode == "adaptive")
	{
		int l = 1, r = 1024;
		int guess;
		while (std::cin >> guess)
		{
			if (guess == l && guess == r)
			{
				std::cout << "=" << std::endl;
				break;
			}
			else if (guess < l)
				std::cout << "<" << std::endl;
			else if (guess > r)
				std::cout << ">" << std::endl;
			else
			{
				int small = guess - l, large = r - guess;
				if (small < large)
					l = guess + 1;
				else
					r = guess - 1;
				if (guess < l)
					std::cout << "<" << std::endl;
				else if (guess > r)
					std::cout << ">" << std::endl;
				else
					assert(false);
			}
		}
		if (std::cin.fail())
			wrong_answer("Failed to read interger from the participant");
	}
	else
		assert(false);

	exit(EXIT_AC);
}