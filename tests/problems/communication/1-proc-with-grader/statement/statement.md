# Number Guessing

The judge has a hidden integer in the range $\{0, 1, \ldots, n - 1}$.
Each time, you can ask the judge a number $x$, and the judge will respond you with whether the hidden number is less than $x$.

## Implementation details

You need to implement the following procedure:
```cpp
int find_number(int n);
```
 - The argument $n$ indicates that the possible hidden integer is betwen $0$ and $n - 1$.
 - In each testcase, this procedure will be called exactly 1 time.

You can call to the following procedure:
```cpp
bool is_less_than(int x);
```
 - The argument $x$ specifies the number you ask the judge about.
 - The return value is `true` if the hidden number is less than $x$, and `false` otherwise.
 - During a single testcase, you can call to this procedure at most $1000$ times.

Note that the judge is **adaptive**, which means the judge can change the hidden number during the grading procedure as long as it is consistence with all previous interactions.

## Constraints

- $1 \leq n \leq 1000$.

## Scoring

TODO: add this section after we have CMS scoring support
