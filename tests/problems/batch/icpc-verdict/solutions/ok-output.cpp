#include <iostream>
#include <string>

// whitediff, this will still pass but outputing ~1 MiB
int main() { std::cout << "answer" << std::string(1024 * 1024, ' ') << '\n'; }
