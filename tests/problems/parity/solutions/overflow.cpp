#include <iostream>
#include <cassert>

int main() {
  int num;
  std::cin >> num;
  std::cout << (num % 2 == 0 ? 0 : 1) << '\n';
}
