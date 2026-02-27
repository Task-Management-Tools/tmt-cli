#include "testlib.h"
#include <string>

const double MAXC = 50;

int main(int argc, char **argv) {
    registerValidation(argc, argv); 
    inf.readStrictDouble(0, MAXC, 0, 5, "a");
    inf.readSpace();
    inf.readStrictDouble(0, MAXC, 0, 5, "b");
    inf.readEoln();
    inf.readEof();
    exit(42);
}
