#include "testlib.h"
#include <string>

const int MAXC = 2000;

int main(int argc, char **argv) {
    registerValidation(argc, argv); 
    inf.readInt(0, MAXC, "x");
    inf.readEoln();
    inf.readEof();
    exit(42);
}
