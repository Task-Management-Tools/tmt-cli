#include <iostream>
#include <string>

int main() { std::cout << "answer" << std::string(3 * 1024 * 1024, ' ') << '\n'; }
