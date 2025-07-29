import math
import time
import os
import signal
import select
import subprocess
import resource
import traceback
from threading import Timer


class Process(subprocess.Popen):
    """
    Extending subprocess.Popen.
    """

    def __init__(self, *args, time_limit: float, memory_limit: int, output_limit: int = resource.RLIM_INFINITY,
                 stdin_redirect=None, stdout_redirect=None, stderr_redirect=None, **kwargs):
        """
        @params time_limit: Generation stage time limit per task (miliseconds).
        @params time_limit: Generation stage memory limit per task (kbytes).
        """

        self.time_limit: float = time_limit
        self.memory_limit: int = memory_limit * 1024 * 1024  # mbytes to bytes
        self.output_limit: int = output_limit

        self.stdin_redirect = stdin_redirect
        self.stdout_redirect = stdout_redirect
        self.stderr_redirect = stderr_redirect

        self._preexec_fn = kwargs.get("preexec_fn", None)
        kwargs["preexec_fn"] = self.prepare

        super().__init__(*args, **kwargs)
        self.popen_time: float = time.monotonic()
        self.poll_time: float
        self.wall_time_limit: float = time_limit + 1000 # add one second on top of that

        self.timer = Timer(self.wall_time_limit / 1000, self.safe_kill)
        self.timer.start()
        self.status: int
        self.rusage: resource.struct_rusage

    def prepare(self):
        try:
            cpu_time = int(math.ceil(self.time_limit / 1000)) + 1
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_time, cpu_time))
            # Single file size limit
            resource.setrlimit(resource.RLIMIT_FSIZE, (self.output_limit, self.output_limit))
            # Address space (virtual memory) limit
            resource.setrlimit(resource.RLIMIT_AS, (self.memory_limit, self.memory_limit))
            # Stack size same as address space
            resource.setrlimit(resource.RLIMIT_STACK, (self.memory_limit, self.memory_limit))

            if self.stdin_redirect is not None:
                stdin_redirect = os.open(self.stdin_redirect, os.O_RDONLY | os.O_CREAT)
                os.dup2(stdin_redirect, 0)
                os.close(stdin_redirect)
            if self.stdout_redirect is not None:
                stdout_redirect = os.open(self.stdout_redirect, os.O_WRONLY | os.O_TRUNC | os.O_CREAT)
                os.dup2(stdout_redirect, 1)
                os.close(stdout_redirect)
            if self.stderr_redirect is not None:
                stderr_redirect = os.open(self.stderr_redirect, os.O_WRONLY | os.O_TRUNC | os.O_CREAT)
                os.dup2(stderr_redirect, 2)
                os.close(stderr_redirect)

            if self._preexec_fn is not None:
                self._preexec_fn()
        except Exception as e:
            traceback.print_exc()
            raise e

    def safe_kill(self):
        # While this has a potential race condition, in practice I don't think the PID will be used
        # up so fast that the ID cycles back to the same one, and that has to occur during the race
        # condition window (that is testing returncode is None to actually sending the signal).
        # There is a Linux 5 solution but the system call is not natively supported by Python.
        if self.returncode is None:
            try:
                self.kill()
                # self.wait4()
            except ChildProcessError:
                pass

    def wait4(self) -> int:
        if self.returncode is None:
            poll_time = time.monotonic()
            pid, status, rusage = os.wait4(self.pid, os.WNOHANG)
            if pid != 0:
                self.status = status
                self.rusage = rusage
                self.returncode = os.waitstatus_to_exitcode(status)
                self.poll_time = poll_time
                self.timer.cancel()
        return self.returncode

    @property
    def get_deadline(self) -> float: return self.popen_time + self.wall_time_limit

    @property
    def cpu_time(self) -> float: return self.rusage.ru_utime + self.rusage.ru_stime
    """This is in seconds."""

    @property
    def wall_clock_time(self) -> float: return self.poll_time - self.popen_time
    """This is in seconds."""

    # This is RSS and not VSS (which is what we acutally want)
    # VSS is still restricted, but still required for TIOJ judge.
    @property
    def max_rss(self) -> int: return self.rusage.ru_maxrss

    # We cannot know with this type of execution, so return 0 instead
    @property
    def max_vss(self) -> int: return 0

    @property
    def exit_signal(self): return os.WTERMSIG(self.status) if os.WIFSIGNALED(self.status) else 0

    @property
    def exit_code(self): return os.WEXITSTATUS(self.status) if os.WIFEXITED(self.status) else 0

    @property
    def is_signaled_exit(self): return os.WIFSIGNALED(self.status) and os.WTERMSIG(self.status) == signal.SIGSEGV

    @property
    def is_timedout(self): return self.poll_time - self.popen_time > self.time_limit


def pre_wait_procs() -> None:

    signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGCHLD})

def wait_procs(procs: list[Process]) -> None:
    """
    Wait until all processes either terminate or meet their deadlines.
    This process muse be used with pre_wait_procs() to block child with too early terminations.
    """
    # Block SIGCHLD so we can wait for it explicitly
    signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGCHLD})
    remaining = procs.copy()
    try:
        while remaining:
            # Wait for a SIGCHLD
            signal.sigwaitinfo({signal.SIGCHLD})

            # Poll with wait4
            still_alive: list[Process] = []
            for proc in remaining:
                if proc.wait4() is None:
                    still_alive.append(proc)

            remaining = still_alive

    except (KeyboardInterrupt, InterruptedError) as exception:
        # Force kill the children to prevent orphans
        # We should never recieve other singals other than SIGINT (and SIGKILL)
        for process in remaining:
            process.safe_kill()
        raise exception # this exception should be unhandled, since the user asked that
    finally:
        signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGCHLD})


def wait_for_outputs(proc: Process) -> list[int]:
    """
    Wait for the conclusion of the processes in the list, avoiding
    starving for input and output.

    procs: a list of processes as returned by Popen.

    return: a list of return codes.

    This function is modified from cms-dev:cms/grading/Sandbox.py#L66.
    """

    stdout, stderr = "", ""

    # Read stdout and stderr to the end without having to block
    # because of insufficient buffering (and without allocating too
    # much memory). Unix specific.
    while proc.wait4() is None:
        to_read = ([proc.stdout] if proc.stdout and not proc.stdout.closed else [] +
                   [proc.stderr] if proc.stderr and not proc.stderr.closed else [])
        if len(to_read) == 0:
            break
        available_read = select.select(to_read, [], [], 1.0)[0]
        for file in available_read:
            content = file.read(8 * 1024)
            if type(content) is bytes:
                content = content.decode()
            if file is proc.stdout:
                stdout += content
            else:
                stderr += content
    return stdout, stderr
