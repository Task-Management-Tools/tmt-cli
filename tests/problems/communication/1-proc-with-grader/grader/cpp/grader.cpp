#include "guess.h"
#include <csignal>
#include <cstdlib>
#include <cstdio>
#include <concepts>
#include <string>
#include <typeinfo>

using namespace std;

namespace
{
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

    bool exit_allowed = false;

    [[noreturn]] void authorized_exit(int exit_code)
    {
        exit_allowed = true;
        exit(exit_code);
    }

    FILE *fin = stdin;
    FILE *fout = stdout;

    void out_flush()
    {
        fflush(fout);
    }

    void write_int(std::integral auto x)
    {
        if (1 != fwrite(&x, sizeof(x), 1, fout))
        {
            fprintf(stderr, "%s", ("Could not write "s + typeid(x).name() + " to fout\n").c_str());
            authorized_exit(3);
        }
    }

    void write_secret(int g2m_code = G2M_CODE__OK)
    {
        write_int(secret_g2m | g2m_code);
    }

    [[noreturn]] void die(int g2m_code)
    {
        if (g2m_code == G2M_CODE__OK)
        {
            fprintf(stderr, "Shall not die with code OK\n");
            authorized_exit(5);
        }
        fprintf(stderr, "Dying with code %d\n", g2m_code);
        if (g2m_code != G2M_CODE__SILENT)
            write_secret(g2m_code);
        fclose(fin);
        fclose(fout);
        authorized_exit(0);
    }

    template <std::integral I>
    I read_int()
    {
        I x;
        if (1 != fread(&x, sizeof(x), 1, fin))
        {
            fprintf(stderr, "%s", ("Could not read "s + typeid(x).name() + " from fin\n").c_str());
            authorized_exit(3);
        }
        return x;
    }

    void read_secret()
    {
        int secret = read_int<int>();
        if ((secret & ~code_mask) != secret_m2g)
            die(G2M_CODE__PV_TAMPER_M2G);
        int m2g_code = secret & code_mask;
        if (m2g_code != M2G_CODE__OK)
            die(G2M_CODE__SILENT);
    }

    void check_exit_protocol()
    {
        if (!exit_allowed)
            die(G2M_CODE__PV_CALL_EXIT);
    }

} // namespace

bool is_less_than(int x)
{
    ::write_secret();
    ::write_int('Q');
    ::write_int(x);
    ::out_flush();

    ::read_secret();
    bool ret = ::read_int<bool>();

    return ret;
}

int main()
{

    signal(SIGPIPE, SIG_IGN);
    atexit(check_exit_protocol);
    at_quick_exit(check_exit_protocol);

    read_secret();
    int n = read_int<int>();

    int ans = find_number(n);

    write_secret();
    write_int('A');
    write_int(ans);
    out_flush();

    authorized_exit(0);
}
