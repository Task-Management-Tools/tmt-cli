#include <iostream>

int main() {
    int n;
    std::cin >> n;
    if (n == 1) {
        std::cout << "answer\n";
    }
    else if (n == 2) {
        std::cout << "0.5\n";
    }
    else if (n == 3) {
        std::cout << "answer\n";
    }
    else {
        std::cout << "wrong\n";
    }
}
