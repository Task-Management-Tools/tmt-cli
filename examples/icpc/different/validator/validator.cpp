#include "testlib.h"
#include <string>

const long long MAXC = 1'000'000'000'000'000;

int main(int argc, char **argv) {
    registerValidation(argc, argv);
    while (!inf.seekEof()) {
        inf.readLong(0LL, MAXC, "a");
        inf.readSpace();
        inf.readLong(0LL, MAXC, "b");
        inf.readEoln();
    }
    inf.readEof();
    exit(42);
}
