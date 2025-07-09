#include "testlib.h"
#include <string>

const int MAXC = 1e9;

int main(int argc, char **argv) {
  registerValidation(argc, argv);
  inf.readInt(1, MAXC, "a");
  inf.readSpace();
  inf.readInt(1, MAXC, "b");
  inf.readEoln();
  inf.readEof();
  // exit(42);
}
