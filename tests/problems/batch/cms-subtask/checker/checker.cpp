#include <algorithm>
#include <fstream>
#include <iostream>

int main(int argc, char **argv)
{
    (void)argc;
    std::ifstream testcase_output(argv[3]);

    double d;
    testcase_output >> d;
    d = std::clamp(d, 0.0, 1.0);

    std::cout << d << std::endl;
    if (d == 0.0)
        std::cerr << "translate:wrong" << std::endl;
    else if (d == 1.0)
        std::cerr << "translate:success" << std::endl;
    else
        std::cerr << "translate:partial" << std::endl;
}
