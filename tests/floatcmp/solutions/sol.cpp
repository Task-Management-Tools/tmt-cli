#include <iostream>
#include <string>

int main()
{
  int n;
  std::cin >> n;
  for (int i = 1; i <= n; i++)
  {
    std::string num;
    std::cin >> num;
    std::cout << num << '\n';
  }
}
