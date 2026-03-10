#include <iostream>
#include <cassert>
#include <signal.h>

int main() {
  int a, b;
  std::cin >> a >> b;
  *((int *)0) = 1;
  std::cout << a + b << '\n';
}
