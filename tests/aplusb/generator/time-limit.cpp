// note: we must not use (including trivial) infinite loop since it might be optimized away
// https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2024/p2809r3.html
#include <unistd.h>
int main() { sleep(60); }
