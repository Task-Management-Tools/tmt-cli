#include "testlib.h"
#include <cassert>
#include <cstdio>

int main(int argc, char *argv[]) {
  if (argc < 2) {
    fprintf(stderr, "Arguments should not be empty.\n");
    return 1;
  }
  registerGen(argc, argv, 1);

  int a = opt<int>(1);
  int b = opt<int>(2);
  printf("%d %d\n", a, b);

  return 0;
}
