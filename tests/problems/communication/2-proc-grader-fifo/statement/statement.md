# Accumulate (2 processes, FIFO)

You have two counters, A and B, both initialized to $0$.

You need to implement the following procedure:
```cpp
int accumulateA(int n);
```
 - This increments the counter A by $n$.
```cpp
int accumulateB(int n);
```
 - This increments the counter B by $n$.

During the judging process, one of the process only gets counter A incremented, and the other only gets counter B incremented.

## Constraints

- $0 \leq n < 256$.
