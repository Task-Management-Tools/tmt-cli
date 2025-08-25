#include "testlib.h"
#include <string>

const int MAXC = 2'000'000'000;

int main(int argc, char **argv) {
  registerValidation(argc, argv);
  inf.readInt(1, MAXC, "a");
  inf.readSpace();
  inf.readInt(1, MAXC, "b");
  inf.readEoln();
  inf.readEof();
  exit(42);
}
