#include <algorithm>
#include <concepts>
#include <csignal>
#include <cstdio>
#include <iostream>
#include <string>
#include <vector>
#include <variant>

using namespace std::literals::string_literals;

[[noreturn]] void quit(double score, const char *verdict, const char *reason, int exit_code = EXIT_SUCCESS)
{
    std::fprintf(stdout, "%.6f\n", score);
    std::fprintf(stderr, "%s\n%s\n", verdict, reason);
    std::exit(exit_code);
}
[[noreturn]] void judge_failure(const char *reason)
{
    quit(0.0, "Judge Failure", reason, EXIT_FAILURE);
}

std::vector<std::FILE *> opened_streams = {};
void close_handler()
{
    for (auto fp : opened_streams)
        std::fclose(fp);
}

void close_file(std::FILE *fp)
{
    if (auto iter = std::find(opened_streams.begin(), opened_streams.end(), fp); iter != opened_streams.end())
    {
        std::fclose(fp);
        opened_streams.erase(iter);
    }
}

inline std::FILE *open_file(const char *name, const char *mode)
{
    std::FILE *file = std::fopen(name, mode);
    if (!file)
        quit(0.0, "Judge Failure", ("Could not open file "s + name).c_str(), EXIT_FAILURE);
    opened_streams.emplace_back(file);
    return file;
}

std::FILE *mgr2sol = nullptr;
std::FILE *sol2mgr = nullptr;

// grader/manager protocol

const int secret_g2m = 0x7F6BA410;
const int secret_m2g = 0XCB7489D0;
const int code_mask = 0x0000000F;

const int M2G_CODE__OK = 0;
const int M2G_CODE__DIE = 1;

const int G2M_CODE__OK = 0;
const int G2M_CODE__PV_CALL_EXIT = 13;
const int G2M_CODE__PV_TAMPER_M2G = 14;
const int G2M_CODE__SILENT = 15;

void out_flush()
{
    fflush(mgr2sol);
}

void write_int(std::integral auto x)
{
    if (!mgr2sol || 1 != fwrite(&x, sizeof(x), 1, mgr2sol))
    {
        close_file(mgr2sol);
        close_file(sol2mgr);
        mgr2sol = sol2mgr = nullptr;
    }
}

void write_secret(int m2g_code = M2G_CODE__OK)
{
    write_int(secret_m2g | m2g_code);
}

[[noreturn]] void die(const char *verdict, const char *reason)
{
    write_secret(M2G_CODE__DIE);
    out_flush();
    quit(0.0, verdict, reason);
}

[[noreturn]] void die_rte(const char *msg)
{
    die("Protocol Violation", msg);
}

template <std::integral T>
T read_int()
{
    T x;
    if (!sol2mgr || 1 != fread(&x, sizeof(x), 1, sol2mgr))
    {
        close_file(mgr2sol);
        close_file(sol2mgr);
        mgr2sol = sol2mgr = nullptr;
        die_rte("manual PV, can't read int from grader");
    }
    return x;
}

void read_secret()
{
    int secret = read_int<int>();
    if ((secret & ~code_mask) != secret_g2m)
        die("Protocol Violation", "Possible tampering with sol2mgr");
    int g2m_code = secret & code_mask;
    switch (g2m_code)
    {
    case G2M_CODE__OK:
        return;
    case G2M_CODE__SILENT:
        judge_failure("Unexpected g2m_code SILENT from sol2mgr");
    case G2M_CODE__PV_TAMPER_M2G:
        die("Protocol Violation", "Possible tampering with mgr2sol");
    case G2M_CODE__PV_CALL_EXIT:
        die("Protocol Violation", "Solution called exit()");
    default:
        judge_failure(("Unknown g2m_code "s + std::to_string(g2m_code) + " from sol2mgr").c_str());
    }
}

// Judge strategies

constexpr int MAX_QUERIES = 1000;

struct fixed_strategy
{
    int hidden;

    fixed_strategy(int x) : hidden(x) {}
    bool is_less_than(int x) { return hidden < x; }
    bool is_correct(int x) { return hidden == x; }
};

struct adaptive_strategy
{
    int l, r;

    adaptive_strategy(int n) : l(0), r(n - 1) {}
    bool is_less_than(int x)
    {
        if (x <= l || r < x)
            return r < x;
        if (x - l <= r - x + 1)
        {
            l = x;
            return false;
        }
        else
        {
            r = x - 1;
            return true;
        }
    }
    bool is_correct(int x) { return l == x && r == x; }
};

int main(int argc, char **argv)
{
    std::atexit(close_handler);
    std::signal(SIGPIPE, SIG_IGN);

    int num_processes = 1;
    {
        int required_args = 1 + 2 * num_processes;
        if (argc < required_args || required_args + 1 < argc)
        {
            std::string usage = argv[0];
            for (int i = 0; i < num_processes; i++)
                usage += " sol" + std::to_string(i) + "-to-mgr mgr-to-sol" + std::to_string(i);

            std::fprintf(stderr, "Invalid number of arguments: %d\nUsage: %s", argc - 1, usage.c_str());
            std::exit(EXIT_FAILURE);
        }
    }

    mgr2sol = open_file(argv[2], "a");
    sol2mgr = open_file(argv[1], "r");

    int n;
    auto strat = [&]() -> std::variant<fixed_strategy, adaptive_strategy>
    {
        char c_mode[256];
        if (std::fscanf(stdin, "%255s%d", c_mode, &n) != 2)
            judge_failure("Cannot read strategy setting");
        if (c_mode == "fixed"s)
        {
            int x;
            if (std::fscanf(stdin, "%d", &x) != 1)
                judge_failure("Cannot read strategy setting");
            return fixed_strategy(x);
        }
        else if (c_mode == "adaptive"s)
            return adaptive_strategy(n);
        judge_failure("Cannot read strategy setting");
    }();

    write_secret();
    write_int(n);
    out_flush();

    int query_count = 0;
    while (true)
    {
        read_secret();
        char op = read_int<char>();
        int x = read_int<int>();

        if (op == 'A')
        {
            bool correct = std::visit([ans = x](auto &&s)
                                      { return s.is_correct(ans); }, strat);
            if (!correct)
                die("translate:wrong", "Incorrect answer");
            break;
        }
        else if (op == 'Q')
        {
            query_count++;
            if (query_count > MAX_QUERIES)
                die("translate:wrong", "Query limit exceeded");

            bool is_less_than = std::visit([query = x](auto &&s)
                                           { return s.is_less_than(query); }, strat);
            write_secret();
            write_int(is_less_than);
            out_flush();
        }
        else
            die("Protocol Violation", "Unknown interaction character");
    }

    if (query_count <= 10)
        quit(1.0, "translate:correct", ("Query = "s + std::to_string(query_count)).c_str());
    else
        quit(0.5, "translate:partial", ("Query = "s + std::to_string(query_count)).c_str());

    quit(0.0, "Judge Failure", "Reached an unreachable code!", EXIT_FAILURE);
    return 0;
}
