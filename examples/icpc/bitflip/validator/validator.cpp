#include "testlib.h"
#include <string>

int main(int argc, char **argv)
{
    registerValidation(argc, argv);

    std::string s = inf.readToken();
    ensure(s == "first");
    inf.readSpace();
    int n = inf.readInt(1, 10'000);
    inf.readEoln();

    for (int i = 0; i < n; i++)
    {
        std::string str = inf.readToken();
        ensure(1 <= str.size() && str.size() <= 20);
        for (auto c : str)
            ensure(c == '0' || c == '1');
        inf.readEoln();
    }
    inf.readEof();
    return 42;
}
