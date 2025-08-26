#include <iostream>
#include <cassert>
#include <cstdlib>

char* large;

int main() {
  long long a, b;

  std::cin >> a >> b;
  
  long long size = (a + b) * 3 / 2;
  large = (char*)malloc(size);
  for (long long i = 0; i < size; i += 16384)
    large[i] = 0;
  std::cout << a + b << '\n';
}
