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
    if (i % 2 == 0)
      std::cout << std::setprecision(20) << num * (1.0 + 1e-7) << '\n';
    else
      std::cout << std::setprecision(20) << num / (1.0 + 1e-7) << '\n';
  }
}
