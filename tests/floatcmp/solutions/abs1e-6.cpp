#include <iostream>
#include <iomanip>
#include <string>
#include <fenv.h>

int main()
{
  int n;
  std::cin >> n;
  for (int i = 1; i <= n; i++)
  {
    double num;
    std::cin >> num;
    if (i % 2 == 0)
    {
      fesetround(FE_DOWNWARD);
      std::cout << std::setprecision(20) << (num + 1e-6) << '\n';
    }
    else
    {
      fesetround(FE_UPWARD);
      std::cout << std::setprecision(20) << (num - 1e-6) << '\n';
    }
  }
}
