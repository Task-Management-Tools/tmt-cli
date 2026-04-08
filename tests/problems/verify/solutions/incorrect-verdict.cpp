#include <iostream>

int main() {
    int n;
    std::cin >> n;
    if (n == 1) {
        for (int i = 0; i < 1'000'000'000; i++)
            std::cerr << ":(\n";
    }
    else if (n == 2) {
        std::cout << "0.7\n";
    }
    else if (n == 3) {
        std::cout << "wrong\n";
    }
    else {
        for (int i = 0; i < 1'000'000'000; i++)
            std::cerr << ":(\n";
    }
}
