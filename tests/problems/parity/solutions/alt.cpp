#include <iostream>
#include <string>

int main() {
  std::string num;
  std::cin >> num;
  std::cout << ((num.back() - '0') % 2 == 0 ? 0 : 1) << '\n';
}
