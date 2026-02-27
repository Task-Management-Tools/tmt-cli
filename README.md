# tmt-cli

Command Line Interface for Task Management Tools

## Quick start

```bash
python3 -m pip install pyyaml

git clone https://github.com/Task-Management-Tools/tmt-cli.git
alias tmt='python3 ~/path/to/tmt-cli/tmt.py'
```

Run from anywhere inside a problem directory. `tmt` searches upward from the current directory to find `problem.yaml`.

## Requirements

- Python `>=3.10`
  - `pyyaml` python package
- `make`
  - `tmt` assumes that GNU Make is used, so if you're on macOS please take care of that (e.g. add `MAKE=gmake`).
- C++ toolchain for `.cpp` and `.cc` sources (e.g. `g++`)

Optional environment variables:

- `MAKE` to override the `make` executable
- `PYTHON` to override the `python3` executable
- `CXX` to override the `g++` executable
- `CXXFLAGS`

## Directory structure

```
problem_root/
├── problem.yaml
├── compiler.yaml
├── recipe
├── verdicts.yaml
├── include/
│   └── headers used by generator/validator/checker, e.g. testlib.h
├── generator/
│   ├── manual/
│   └── *.cpp, *.cc, *.py
├── validator/
│   └── *.cpp, *.cc, *.py
├── solutions/
│   └── reference/incorrect solutions
├── checker/ (optional)
├── interactor/ (interactive only)
├── statement/
│   └── all statement-related files
├── testcases/ (auto generated)
│   ├── hash.json
│   └── summary
├── logs/ (auto generated)
└── sandbox/ (auto generated)
```

## Commands

- `tmt gen` compiles the required binaries and generates testcases based on `recipe`.
  - `[--verify-hash]` regenerates testcases and compares testcase SHA-256 hashes to existing `testcases/hash.json`. Aborts if `hash.json` doesn't exist or the hashes are different.
    - The `hash.json` file will be generated (or overwritten) if `--verify-hash` is not specified.
    - We recommend tracking `hash.json` in git (or any VCS you're using).
  - `[-r|--show-reason]` prints generator/validator/checker failure reasons verbosely.
- `tmt invoke solutions/correct.cpp` compiles the submission `solutions/correct.cpp` and runs it against the generated testcases.
  - `[-r|--show-reason]` prints submission failure reasons verbosely.
- `tmt clean` removes generated testcases, logs, sandbox, and compiled binaries.
  - `[-y|--yes]` skips confirmations.
- `tmt export output.zip` exports the generated testcases to `output.zip`.
  - The format is determined by `problem.yaml:judge_convention` and currently only `icpc` is supported.

## `problem.yaml`

### Example: A + B Problem (`icpc + batch` with default checker)

```yaml
title: A + B Problem
short_name: aplusb
description: A + B Problem

# these two fields must start with .
input_extension: .in
output_extension: .out

judge_convention: icpc
problem_type: batch

validator:
  type: default

solution:
  type: default
  time_limit: 1000 ms
  memory_limit: 1 GiB
  output_limit: unlimited

answer_generation:
  type: solution
  filename: sol.cpp

compile_time_limit: 60 s
compile_memory_limit: unlimited

tmt_version: 0.1.0
```

Explanation:

- `input_extension` and `output_extension` specify the extension of the generated testcase files.
- `solution.time_limit` accepts `ms` or `s`.
- `solution.memory_limit` accepts `M`, `MiB`, `G`, or `GiB`.
  - Note that `M` = `MiB` and `G` = `GiB`.
- `solution.output_limit` accepts the same units or `unlimited`.
- `answer_generation.filename` specifies what the reference solution is.

### Other Examples

For other examples, please check the `examples/` folder in this repository.

| Example                    | Type                 | Details                        |
|----------------------------|----------------------|--------------------------------|
| `examples/icpc/add/`       | `icpc + batch`       | default checker                |
| `examples/icpc/different/` | `icpc + batch`       | default checker                |
| `examples/icpc/floatadd/`  | `icpc + batch`       | default checker with arguments |
| `examples/icpc/revadd/`    | `icpc + batch`       | custom checker                 |
| `examples/icpc/guess/`     | `icpc + interactive` | interactor                     |

todo: examples of `checker.check_generated_output` and `checker.check_forced_output`

## `compiler.yaml`

### Example

```yaml
cpp:
  flags: ["-std=gnu++20", "-O2", "-Wall", "-Wextra", "-Wshadow", "-Wconversion"]
```

- Specify the flags to compile all C++ files.
- You can use `CXXFLAGS` environment variable to temporarily override it.
  - Example: `CXXFLAGS="-fsanitize=undefined" tmt invoke some.cpp`
  - Notice that by default `tmt` may add some additional flags to mitigate some platform-dependent issues, but if you specified `CXXFLAGS`, `tmt` won't do that for you.

## `verdicts.yaml`

### Example

```yaml
- filename: sol.cpp
  verdict: accepted
- filename: sol.py
  verdict: accepted
- filename: overflow.cpp
  verdict: wrong_answer
```

- It should contain the information of the expected verdict of the submissions in `solutions/`.
  - Currently, it is only used by `tmt export` to categorize `solutions/` into verdict folders.
  - We are planning to add a `tmt verify` command that will rely on this file.

## Recipe syntax

`recipe` defines how to generate testcases. Lines are either commands (starting with `@`) or generator commands.

### Example

```text
@global_validation myvalidator

@testset samples
manual s1.in
manual s2.in

@testset handmade
print 30 11 | swap
print 30 22 | swap
print 47 24
print 2147483647 1
print 2147483647 2147483647
manual 1.in
```

- Generator executables, like `print` or `swap`, are resolved in `generator/` subfolder.
  - For instance, `tmt` will use the compiled version of `generator/print.cpp` for `print` (or `print.py`, if you're using python)
- `tmt` will take the standard output of the generator executable as the testcase input.
  - The testcase output would typically be generated by running the reference solution against the inputs.
- `manual <input>` uses a file from `generator/manual/` as the testcase input.
- Testcases are named as `<testset-index>_<testset-name>_<testcase-index>`, with zero-padding based on counts.

### Basic `@` commands

- `@testset <name>` starts a new testset.
- `@global_validation <executable ...>` adds a validator for all testcases.
  - The validator executable is resolved in `validator/` subfolder.
  - In this example, `@global_validation myvalidator` means that all testcases should pass the validation of `validator/myvalidator.cpp`
  - Note that in ICPC convention, validators must exit with code `42` to pass.
- `@validation <executable ...>` adds a validator for the current testset or subtask.

### Advanced usage

- `@subtask <name> <score>` starts a new subtask. If test lines appear inside a subtask, an independent testset is created with the same name.
  - Note that the names of testsets and subtasks should be distinct.
  - The difference from "testset": subtasks have scores, and subtasks can `@include` testsets or other subtasks.
- `@description <text>` sets description for the current testset or subtask.
- `@include <testset-or-subtask>` includes a testset or all testsets from another subtask into the current subtask.
- `@constant <NAME> <value>` defines a constant used as `${NAME}` in later lines.
- `@extra_file <NAME> <.ext>` creates an extra file with the filename `<testcase-name><.ext>` for each testcase in the current testset or subtask. This enables generators to externally store auxiliary information for their generated testcases.
  - For instance, using `@extra_file FIGURE .png` allows generators to generate corresponding visualizations along with the test cases.
  - Note that generators are responsible for opening these files. Users should pass the filenames by including the defined constant `${NAME}` in the generation command (e.g., `gen --figure=${FIGURE}`).
- `manual <input> <output>` (`manual` but with an additional argument `<output>`) forces the testcase output to a file from `generator/manual/` and marks it as forced output for checker rules.
- Piped sequences
  - A generator command can be a shell-like pipeline sequence of executables, split by `|`. (e.g. `step1 args1 | step2 args2`)
  - The previous command's output will be the next command's input.
  - The last command's stdout will be used.
  - Validation commands do not support pipes.

## License

The default validator from the [Kattis problemtools](https://github.com/Kattis/problemtools) package is included, licensed under the MIT license. See [icpc_default_validator.cc](internal/steps/checker/default_checkers/icpc_default_validator.cc).
