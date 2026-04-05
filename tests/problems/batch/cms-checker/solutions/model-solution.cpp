#include <iostream>
#include <string>

int main()
{
  std::string input;
  std::cin >> input;
  if (input != "input")
    return -1;
  std::cout << "answer\n";
}
