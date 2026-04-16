# TMT Recipe Syntax

TMT generates and manages test cases based on the `recipe` file.

- [TMT Recipe Syntax](#tmt-recipe-syntax)
  - [Characters](#characters)
  - [Lines](#lines)
  - [Words](#words)
    - [Quoting](#quoting)
    - [Comments](#comments)
  - [Generation Sequences](#generation-sequences)
  - [Keywords](#keywords)
    - [`@testset` and `@subtask`](#testset-and-subtask)
    - [`@include`](#include)
    - [`@constant`](#constant)
    - [`@description`](#description)
    - [`@validation` and `@global_validation`](#validation-and-global_validation)
    - [`@extra_file`](#extra_file)

## Characters

In TMT, there are three types of characters:

- Whitespace characters.  
  They are the [ASCII](https://en.wikipedia.org/wiki/ASCII) whitespaces:
  - 0x0A new line,
  - 0x0B vertical tab,
  - 0x0C form feed,
  - 0x0D carriage return, and
  - 0x20 space.
- Plain characters.  
  - digits `0-9` (0x30 -- 0x39),
  - upper case Latin alphabet `A-Z` (0x41 -- 0x5A).
  - lower case Latin alphabet `a-z` (0x61 -- 0x7A).
  - Hyphen-minus `-` (0x2D).
  - Underscore `_` (0x5F).
- Special characters.  
    These are the ASCII printable characters, **except** for whitespaces, plain characters, and the below:
  - ampersand `&` (0x26),
  - star `*` (0x2A),
  - forward slash `/` (0x2F),
  - colon `:` (0x3A),
  - semicolon `;` (0x3B),
  - less than `<` (0x3C),
  - greater than `>` (0x3E),
  - question mark `?` (0x3F),
  - backward slash `\` (0x5C), and
  - backtick <code>`</code> (0x60).

Whitespace, plain, and special characters are collectively called base characters.


## Lines

In TMT, each line is considered a single command.
Each command can be a generation sequence or keyword command.

If a line does not follow the specification, then the line is *ill-formed*.
Recipes with any ill-formed line are rejected by the tool and diagnostics will be provided for each of those lines.

## Words

Each line in a TMT recipe is parsed into a sequence of words.

For each line, the leading and trailing whitespaces are removed.
The word sequence is formed by repeatedly extracting valid words from the line by the following process.

1. Remove the leading whitespace characters.
2. If the line is exhausted, finish the word sequence parsing.
3. Extract a word according to the [quoting rule](#quoting).
4. If no word can be extracted, the line is ill-formed.
5. If the word forms a valid [comment](#comments), the word and the rest of the line is discarded.
6. If the word is the first in the sequence, is unquoted, and exactly matches `@description`, then the word sequence parsing ends.
   For this specific case, see keyword [`@description`](#description).

If the sequence is empty, the line is ignored.
If the first word is unquoted and starts with `@`, it is considered a [keyword command](#keywords); otherwise, it is a [generation sequence](#generation-sequences).

For example,
```
@testset group1
'@testset' group2
```
means different things.
The first one means to use the keyword `@testset` with arguments `group1`, while the second one simply specifies the [command sequence](#command-sequence) `@testset` with arguments `group2` because the first word is quoted, so it no longer refers to the keyword.


### Quoting

In TMT, each word can be quoted.
You can use quoting to enclose any sequence of base characters:

```
gen "I'm TAS" ''
```
will be properly split into three words: `gen`, `I'm TAS`, and an empty word.

In particular, there are three types of words:
- A string surrounded with double quotes (`"`) and does not contain any double quote is called a *double-quoted* word.
- A string surrounded with single quotes (`'`) and does not contain any single quote is called a *single-quoted* word.
- A string not starting with either of the quotes is called a *plain* word.

All words can only contain base characters.

Note that, a word starting with any kind of quote but not closed before the end of the line, is considered ill-formed.
For example,
```
gen "this is not closed...
```
is ill-formed.

If a word is quoted, the word represents the content without the surrounding quotation marks.
Otherwise, the word is treated as-is.

### Comments

TMT recipe file recognizes single line comments.
An unquoted word starting with the number sign (`#`) comments out the rest of a line:
```
gen 8 fixed  # generates the special case when N = 8
```


For example, all of the following forms valid comments:
```
gen #
gen #still a comment
gen # definitely a valid comment
```
However, quoted and words containing `#` in between will **not** be considered as valid comments:
```
gen not comment#
gen '# not comment'
gen '#' not comment
```
are all lines without comments.

## Generation Sequences

Each generation sequence generates one test case.
Before the generation process, each file recognized by TMT in directory `generator` will be compiled to a generator named by the stem (base name; the part without the file extension) of the filename generated.
If multiple source files would yield the same name, TMT aborts and reports the error.

In generation sequence, each unquoted word equal to a single pipe character (`|`) is called a *pipe*.
The word sequence is first split into generation commands by pipes.
Each component represents a generation command, which represents a process when generating the test case:
 - The first word of each command is the name of the generator.
   - If the generator name is an unquoted special keyword `manual`, it copies the file found in `generator/manual` to the standard output.
 - The remaining words of each command are the parameters to the generator.
If any generation command is empty, the line is ill-formed.

Generator processes are chained by pipes and the last generator output is used as the test case input.
In particular:
 - The first process receives nothing from the standard input.
 - Each process, except for the last one, receives standard input from the standard output of the previous process via a pipe.
 - The last process output is the test case input.
 - The standard error of each process is kept as log files.

If any of the process exists with a non-zero code, the generation sequence fails.

Each generation sequence must be belong to a testset or subtask scope, see [`@testset` and `@subtask`](#testset-and-subtask).

## Keywords

To specify the structure of the test data, TMT recipes provide a set of keywords.

The first word specifies the keyword command, and it must follow the respective format and constraints, or the line is considered ill-formed.


Here is the list of all keywords:

<!-- no toc -->
- [`@testset` and `@subtask`](#testset-and-subtask)
- [`@include`](#include)
- [`@constant`](#constant)
- [`@description`](#description)
- [`@validation` and `@global_validation`](#validation-and-global_validation)
- [`@extra_file`](#extra_file)

### `@testset` and `@subtask`

`@testset` and `@subtask` are used to declare testsets and subtasks.

```
@testset <name>
@subtask <name> <score>
```
- `name`: the name of the testset/subtask.  
  The name can only contain plain and special characters (i.e. base characters other than whitespaces).
  Each testset and subtask must have a unique name.
- `score`: the score of the subtask.  
  It must be a real number between $-10^{100}$ and $10^{100}$.
  The score is in C-style floating point decimal constant format.
  It accepts decimal numbers and scientific notations, which is described by the following BNF:
  ```
  <float>       :=  <signed-frac> | <signed-frac> <exp>
  <signed-frac> :=  <sign-opt> <frac>
  <frac>        :=  <digit-seq> '.' <digit-seq> |
                    <digit-seq> '.' |
                    '.' <digit-seq>
  <exp>         :=  'e' <sign-opt> <digit-seq> |
                    'E' <sign-opt> <digit-seq>
  <sign-opt>    :=  '+' | '-' | ''
  <digit-seq>   :=  <digit> | <digit-seq> <digit>
  <digit>       := '0' | '1' | ... | '9'
  ```
  If you need to use [Guaissan integers ($\mathbb Z[i]$)](https://en.wikipedia.org/wiki/Gaussian_integer) as score parameters, see this [guide](https://github.com/Task-Management-Tools/tmt-cli/compare).
  <!-- TODO: when we have CONTRIBUTING.md, change this link -->

As the name suggests, `@testset` starts a new testset, while `@subtask` starts a new subtask.
We call this a *testset/subtask scope*.
Before the first one is declared, the scope is called the *global scope*.

Intuitively, the created testset or subtask contains every generation sequence after this command, until another one (any of testset or subtask) starts.

In TMT, the score computation uses Python `float`.
In practice, scores are usually integers between 0 and 100.
If you need unusual score values (very large or small scores), please be aware of floating point precision loss and range limitations.

<!-- For convenience, we collectively call subtask and testset as *test groups* and testset/subtask scopes as *group scopes*. -->

### `@include`

`@include` specifies the dependency of the current testset or subtask.

```
@include <name>
```
- `name`: the name of the testset/subtask.  
  It must only contain plain and special characters (i.e. base characters other than whitespaces) and is an existing subtask or testset name before this command.

`@include` command can only exist in testset/subtask scopes.
It makes every test case in the included testset/subtask effectively also belong to the current one, without copying them.
The inclusion relation is transitive.
That is, if C includes B and B includes A, C will also contains all test cases from A.

In problems with subtasks, it is very common for a subtask to include previous subtasks with tighter constraints.
`@include` is exactly designed to represent this dependency.
For example,
```
@subtask small 10
gen -N 10 A
gen -N 10 B
gen -N 10 C

@subtask medium 20
@include small
gen -N 400
gen -N 500 A
gen -N 500 B
```
Now subtask medium includes all test cases in subtask small.
Any solution now needs to pass all 6 test cases in order to get accepted on subtask medium.
This operation does not duplicate the testcases; the test cases in subtask small is judged exactly once, but the result is automatically propagated to subtask medium.

If an `@include` command includes itself, it is effectively a no-op.

### `@constant`

`@constant` declates a constant that will be expanded in some other commands.
```
@constant <name> <value>
```
 - `name`: the name of the constant.  
   It must be a constant name not used in the global scope and the current scope, containing only plain characters.
 - `value`: the value of the constant.


Constants lives within their respective scopes: in the global scope, it will be always available after its definition.
In a testset/subtask scope, constants will vanish when the scope ends.

To use a constant for variable expansion, put the name between `${` and `}`.
For example,
```
@constant MAX-N 200

@testset small
@constant SMALL-N 10
gen ${SMALL-N} A
gen ${SMALL-N} B

@testset large
gen ${MAX-N}
```
expands to
```
@testset small
gen 10 A
gen 10 B

@testset large
gen 200
```

Constant expansion takes places after splitting a line to sequence of words and recognizing the comments.
All of the recipe supports constant expansion except for the three cases below.

 - Single-quoted words does not participate in constant expansion.
 - Comments does not participate in constant expansion.
 - Keyword lines [`@testset`](#testset-and-subtask), [`@subtask`](#testset-and-subtask), [`@include`](#include), [`@constant`](#constant), and [`@extra_file`](#extra_file) does not participate in constant expansion.

In these cases, the variable references `${...}` will all stay as-is.

This means, in the following example,
```
@testset hidden
@constant ARGS 'adaptive mixed'
@constant COMMENT '#not a comment'
gen ${ARGS} ${COMMENT} '${ARGS}'
```
gives four words on line 3: `gen`, `adaptive mixed`, `#not a comment`, and `${ARGS}`.
The second word is not split, the third word does not trigger comment detection, and the last word is kept verbatim since it is enclosed in single quotes.

When expanding constants, if any variable references `${...}` uses a name that does not exist, the line is ill-formed.
Fif new variable references `${...}` is formed after some constants expansion, the line is also ill-formed.
This means you cannot try to nest constant expansions or construct it from several constants.


### `@description`

`@description` adds textual description to a testset or subtask.
```
@description ...
```

Keyword lines does not follow the usual word sequence splitting rule.
After `@description` is identified, the parser removes leading and ending white spaces of the remaining part.
The result participates in constant expansion and is set as the description of the testset or subtask verbatim.

For example,
```
@constant MAX-N 1000
@testset small
@description    that's a small testset!

@testset large
@description    N <= ${MAX-N}?! only #1 can solve this set
```
will give descriptions `that's a small testset!` and `N <= 1000?! only #1 can solve this set` to testset small and large, respectively.

`@description` it cannot be used in the global scope.
Each testset and subtask can contain at most one `@description`, the second `@description` and onwards is ill-formed.

### `@validation` and `@global_validation`

`@validation` and `@global_validation` add validations to the testcases.
```
@validation <validation command>
@global_validation <validation command>
```
- `validation command`: a validation command.

Validators are prepared similarly to generators, except that it is found and compiled in directory `validator` and called validators.

Validation commands are almost identical to generator commands.
Each of the validation commands represents a validation to be run determine as follows.

 - The first word of a validation command is the name of the validator.
   - There is no special keyword called `manual`.
 - The remaining words of a validation command are the parameters to the generator.
 - Any single unquoted pipe in validation sequence is invalid.
 - Empty validation sequence is invalid.

The validator receives the test case input as the standard input.
It must exit with the specific code to signify the test case input is valid.
 - In ICPC judge convention, the code is 42 (see [ICPC package format](https://icpc.io/problem-package-format/spec/2025-09.html#exit-codes)).
 - In other judge conventions, the code is 0.

`@global_validation` adds the validation for all test cases, including those added in the future.
`@validation` adds validation to the current testset/subtask.

Testset and subtask validations will be run for every test case in this subtask, including those in depedencies.
The ordering bewteen `@validation`, [`@include`](#include), and other test cases does not matter; validation applies to all test cases and dependencies in the scope.


### `@extra_file`

`@extra_file` adds extra files associated to the test cases.
```
@extra_file <name> [ext]
```
- `name`: the name of the constant.  
  It must be a constant name not used in the global scope and the current scope, containing only plain characters.
- `ext`: the file extension of the extra file.  
  `ext` must start with a dot, and other characters must be plain characters.
  If an `@extra_file` with the same name is defined in other scopes before, then `ext` can be omitted and the value will be whatever it is in the previous definition.
  However, the same name should not map to another file extension, even across unrelated scopes.

The name will be declared to be a special constant that expands to the filename used to store the extra file when generating the test case.

If it is defined in global scope, every test case will have this extra file; if it is defined in testset/subtask scope, it only applies to the immediate test cases inside it and **will not propagate through dependencies**.

When the special constant defined by `@extra_file` is used in validation commands, all dependency testsets/subtasks must also have this special constant defined.
Otherwise, **the validation keyword line** is ill-formed.
