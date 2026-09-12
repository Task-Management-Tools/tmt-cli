# Config `problem.yaml`

Config `problem.yaml` specifies the basic properties of the problem.

The following YAML describes all available keys:
```yaml
title:                    # string
short_name:               # string
description:              # string, optional
input_extension:          # string, starts with .
output_extension:         # string, starts with .
judge_convention:         # string, "icpc|cms"
problem_type:             # string, "batch|interactive|communication|output-only"
tmt_version:              # string
compile_time_limit:       # time limit
compile_memory_limit:     # byte limit (allow unlimited)

validator:
  type:                   # string, "default"

solution:
  time_limit:             # time limit
  memory_limit:           # byte limit (does not allow unlimited)
  output_limit:           # byte limit (allow unlimited)
  type:                   # string, "default|grader"
  grader_name:            # string
  num_procs:              # integer
  use_fifo:               # boolean

answer_generation:
  type:                   # string, "default"
  filename:               # string

checker:
  type:                   # string, "default|custom"
  filename:               # string
  arguments:              # string, optional
  check_generated_output: # boolean, default true
  check_forced_output:    # boolean, default true

interactor:
  filename:               # string
  arguments:              # string

manager:
  filename:               # string

extra:                    # anything
```

## Field Formats

TMT uses YAML 1.1 (by PyYAML).
Boolean, integer, and string fields are parsed accordingly.

In string fields, some inputs may be narrowed to other types (for example, `true`, `false`, `yes`, `no` for boolean types, and integer and floating-point literals).
TMT will report a type mismatch error in these cases.
It can be solved by quoting the string.

In fields where a time (limit) is expected, the format is a nonnegative integer or decimal, followed by spaces, and followed by `s` or `ms`.
The suffix `s` denotes seconds and `ms` denotes milliseconds.

In fields where a byte (limit) is expected, the format is a nonnegative integer, followed by spaces, and followed by `M`, `MiB`, `G`, or `GiB`.
The suffix `M` and `MiB` denote mebibytes ($2^{20}$ bytes); `G` and `GiB` denote gibibytes ($2^{30}$ bytes).

Any optional field can be completely omitted.

Any invalid field name will trigger an error (except for `extra`; see [Root](#root)).

## Root

Currently, TMT supports [DOMjudge](https://github.com/DOMjudge/domjudge) and [Contest Management System](https://github.com/cms-dev/cms).
The following specification refers to them as "DOMjudge" and "CMS", respectively.

- `title`: Title of the problem.
- `short_name`:
- A short name of the problem.
  On DOMjudge, this will be the problem ID.
  On CMS, this will be the problem short name (the name visible on the scoreboard header).
  It is highly recommended not to contain space characters.
- `description`: An optional description of the problem.
- `tmt_version`:
  The version of TMT which the problem package uses.
  Currently, this field does not have practical effect.
  However, in the future, it may be used to support backwards compatibility.
  - For developers, a special string `latest` can be used when the problem (for example, in tests) must be valid in the latest TMT version.
- `input_extension`:
  The file extension for the test case input files.
  It affects generators and validators but not exported packages.
  It must start with a dot (`.`).
- `output_extension`:
  The file extension for the test case output files.
  It affects generators and validators but not exported packages.
  It must start with a dot (`.`).
- `judge_convention`:
  The judge convention TMT follows.
  Must be one of:
  - `icpc`: On platforms where ICPC-style problems are supported.
  - `cms`: CMS.
- `problem_type`:
  The type of the problem.
  Must be one of:
  - `batch`: Typical problems where submissions receive an input and must produce an output.
  - `interactive`:
    ICPC/Codeforces style interactive problems.
    Submissions interact with the interactor through input and output streams.
  - `communication`:
    CMS style communication (interactive) problems.
    Submissions interact with the manager through input and output streams.
    The main difference between this and `interactive` is that the compiled program may be run as multiple instances and interacts with the manager independently.
  - `output-only`:
    Output only problems.
    The test case inputs are given in advance and submissions are the produced outputs.
- `compile_time_limit`:
  The compilation time limit TMT allows for every file, in the time limit format.
  It is a safeguard for TMT and is never exported to the packages.
  Defaults to 60 seconds.
- `compile_memory_limit`:
  The compilation memory limit TMT allows for every file, in the byte limit format.
  It is a safeguard for TMT and is never exported to the packages.
  Defaults to unlimited.
- `validator`: See [Validator](#validator).
- `solution`: See [Solution](#solution).
- `answer_generation`: See [Answer Generation](#answer-generation).
- `checker`: See [Checker](#checker).
- `interactor`: See [Interactor](#interactor).
- `manager`: See [Manager](#manager).
- `extra`: Accepts anything. It is intentionally dropped and ignored by TMT.

Note: not all combinations of `judge_convention` and `problem_type` are supported based on the judge.
Currently:
 - `icpc` supports `batch` and `interactive`.
 - `cms` supports `batch`, `communication`, and `output-only`.
   - Please use `communication` for `interactive` problems.

## Validator
Specifies validation of generated test cases.

- `type`: Must be `default`. It is the only supported mode.

## Solution
Specifies invocation of submissions (solutions).

- `time_limit`: Time limit, in the time limit format.
- `memory_limit`:
  Memory limit, in the byte limit format.
  Memory limit only applies to RSS (resident set size) and does not accept unlimited.
- `output_limit`:
  Output limit, in the byte limit format.
  Accepts unlimited, but:
  - In ICPC format, a suitable output limit must be used.
  - In CMS format, the system-wide default output limit is 1 GB (refer to the [CMS document](https://cms.readthedocs.io/en/latest/Troubleshooting.html#sandbox)).
    TMT will respect the config in YAML, but it is currently **not exported** in the package since it is not representable.
- `type`: Must be one of:
  - `default`: The submission source code is compiled standalone.
  - `grader`: The submission source code is compiled with a grader.
    It is only supported when `judge_convention` is `cms`.
- `grader_name`: The base name of the grader (without file extension).
  This config should be present if and only if `type` is `grader`.


### Communication Task Specific Configs
The following fields must be present when the task type is `communication` and absent otherwise.

- `num_procs`: Number of processes run for each test case. It must be between 1 and 10 due to restrictions of CMS.
- `use_fifo`: Whether to use FIFO in the submission processes.

  Note that the manager will always receive FIFO pairs, even if `num_procs` is set to 1.

  TMT does **not** export this option yet because it is hardcoded in the TPS importer of CMS.
  Following the importer default, it should be `true` for CMS version <= 1.5.1 and `false` if > 1.5.1 or using most of the IOI forks.
  This option is always configurable in the CMS admin interface, in case the configured value is different from the default.

## Answer Generation
Specifies generation of answers (reference outputs).

- `type`: Must be `default`. It is the only supported mode.
- `filename`: The filename of the model solution, relative to `solution/`.

This config supports a shorthand:
```yaml
answer_generation: $filename
```
is equivalent to
```yaml
answer_generation:
  type: default
  filename: $filename
```

## Checker
Specifies the checker (output validator in ICPC, or comparator in CMS).
This config section **must not be present** when `problem_type` is `interactive` or `communication`.

- `type`: Must be one of:
  - `default`: Use the default checker based on the judge convention.
  - `custom`: Use a custom checker.
- `filename`:
  Must not ne present when `type` is `default`.
  When `type` is `custom`, specifies the filename of the checker source file, relative to `checker/`.
- `arguments`:
  Optional field for additional command-line arguments appended to the default arguments.
  The field expects a string.
  The command-line argument list is obtained by splitting by space characters.
  - Note that, when `judge_convention` is `cms`, this field must not be present or empty.
    CMS doesn't support additional arguments for checkers (comparators).
- `check_forced_output`:
  Whether to run the checker when the answer file is copied using the `manual` keyword.
- `check_generated_output`:
  Whether to run the checker when the answer file is produced by the generation sequence but not by the `manual` keyword.
  When the test case answers are not valid outputs (for example, hidden part of the input),
  set this option to `false` to not run the checker in these test cases.
  In certain scenarios (for example, when the answer provably always exists), it can also be used to allow empty answer files to save storage space.

This config supports a shorthand:
```yaml
checker: $filename
```
is equivalent to
```yaml
checker:
  type: custom
  filename: $filename
```

## Interactor
Specifies the interactor.
This config must be present if the task type is `interactive` or absent otherwise.

- `filename`: File name of the interactor, relative to `interactor/`.
- `arguments`: Optional field for additional command-line arguments appended to the default arguments.

This config supports a shorthand:
```yaml
interactor: $filename
```
is equivalent to
```yaml
interactor:
  filename: $filename
```
## Manager
Specifies the manager.
This config must be present when the task type is `communication` and absent otherwise.

- `filename`: File name of the manager, relative to `manager/`.

This config supports a shorthand:
```yaml
manager: $filename
```
is equivalent to
```yaml
manager:
  filename: $filename
```
