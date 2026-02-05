#include <iostream>
#include <iomanip>
#include <string>

int main()
{
  int n;
  std::cin >> n;
  for (int i = 1; i <= n; i++)
  {
    double num;
    std::cin >> num;
    std::cout << std::setprecision(20) << num << '\n';
  }
}
