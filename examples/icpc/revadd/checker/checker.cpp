#include "testlib.h"

// ./checker judge_in(input) judge_ans feedback_dir [additional_arguments] < team_out [ > team_input ]

/* For note
 inf: judge_in
 ouf: team_out
 ans: judge_ans
 */

const int MAXC = 1000;

int main(int argc, char* argv[]) {
    registerTestlibCmd(argc, argv);

    int x = inf.readInt();

    int a = ouf.readInt(0, MAXC);
    int b = ouf.readInt(0, MAXC);
				
    if (a + b != x)
        quitf(_wa, "a + b != x");

    quitf(_ok, "a + b = x");
}
