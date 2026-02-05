#include "testlib.h"
#include <string>

int main(int argc, char **argv)
{
    registerValidation(argc, argv);
    
    std::string s = inf.readToken();
    ensure(s == "fixed" || s == "adaptive");
    if (s == "fixed")
    {
        inf.readSpace();
        inf.readInt(1, 1024);
    }
    inf.readEoln();
    inf.readEof();
    exit(42);
}
