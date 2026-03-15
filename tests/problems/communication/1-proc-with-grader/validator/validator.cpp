#include "testlib.h"
#include <string>

int main(int argc, char **argv)
{
    registerValidation(argc, argv);

    std::string s = inf.readToken();
    inf.readEoln();
    ensure(s == "fixed" || s == "adaptive");
    int n = inf.readInt(1, 1000);
    inf.readEoln();
    if (s == "fixed")
    {
        inf.readInt(0, n - 1);
        inf.readEoln();
    }
    inf.readEof();
}
