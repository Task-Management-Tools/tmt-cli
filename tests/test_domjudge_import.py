from pathlib import Path
from dataclasses import dataclass, field
import os
import re
import shutil
import subprocess
import itertools
import time
import textwrap
from typing import cast

import pytest

from internal.commands.clean import command_clean
from internal.commands.export import command_export
from internal.commands.gen import command_gen
from internal.context import TMTContext
from internal.exporters import DOMJudgeLegacyExporter
from internal.formatting import TerminalFormatter

_counter = itertools.count()
_AUTH = ("robot", "titanium")
_JUDGE_TIME_LIMIT_PER_TASK = 30

_DOMJUDGE_SCRIPT_PATH = Path(__file__).parent.resolve() / "domjudge"


class VagrantEnvironment:
    def __init__(self):
        assert shutil.which("vagrant") is not None

    def environment(self):
        result = self._get_output(["status", "--machine-readable"])
        state = None
        for line in result.stdout.splitlines():
            row = line.split(",")
            if len(row) >= 3 and row[2] == "state":
                state = row[3]

        # launch the VM
        match state:
            case "not_created" | "shutoff":
                self._run(["up"])
            case "paused":
                self._run(["resume"])
            case "running":
                pass
            case _:
                raise ValueError(
                    f"Error starting up Vagrant VM: unknown vagrant state {state}"
                )

        yield self

        # restore the VM to the previous state
        match state:
            case "not_created":
                self._run(["destroy", "-f"])
            case "shutoff":
                self._run(["halt"])
            case "paused":
                self._run(["suspend"])
            case "running":
                pass
            case _:
                raise ValueError(
                    f"Error restoring Vagrant VM: Unknown vagrant state {state}"
                )

    def _run(self, cmd: list[str]):
        return subprocess.check_call(["vagrant"] + cmd, cwd=_DOMJUDGE_SCRIPT_PATH)

    def _get_output(self, cmd: list[str]):
        return subprocess.run(
            ["vagrant"] + cmd,
            cwd=_DOMJUDGE_SCRIPT_PATH,
            capture_output=True,
            text=True,
            check=True,
        )

    def configure_cgroup(self, version: int):
        self._run(["provision", "--provision-with", f"cgroupv{version}"])
        self._run(["reload"])

    def cleanup_domjudge(self, domjudge_version_string: str):
        self._run(
            [
                "ssh",
                "-c",
                f"cd /vagrant && DOMJUDGE_VERSION={domjudge_version_string} ./clean.sh",
            ]
        )

    def startup_domjudge(self, domjudge_version_string: str):
        self._run(
            [
                "ssh",
                "-c",
                f"cd /vagrant && DOMJUDGE_VERSION={domjudge_version_string} ./run.sh",
            ]
        )

    def get_ip(self):
        vm_hostname = self._get_output(["ssh", "-c", "hostname -I"])
        vm_ip = vm_hostname.stdout.strip().split()[0]
        return vm_ip


class HostEnvironment:
    def __init__(self):
        if "GITHUB_RUN_ID" not in os.environ:
            pytest.skip("quitting: not running on GitHub CI")

    def environment(self):
        yield self

    def configure_cgroup(self, version: int):
        output = subprocess.run(
            ["grep", "cgroup", "/proc/filesystems"], capture_output=True, text=True
        ).stdout
        found_version = 2 if "cgroup2" in output else (1 if "cgroup" in output else 0)
        if found_version != version:
            pytest.skip("cgroup version not supported on host")

    def cleanup_domjudge(self, domjudge_version_string: str):
        return subprocess.check_call(
            "./clean.sh",
            cwd=_DOMJUDGE_SCRIPT_PATH / "scripts",
            env=os.environ | {"DOMJUDGE_VERSION": domjudge_version_string},
        )

    def startup_domjudge(self, domjudge_version_string: str):
        return subprocess.check_call(
            "./run.sh",
            cwd=_DOMJUDGE_SCRIPT_PATH / "scripts",
            env=os.environ | {"DOMJUDGE_VERSION": domjudge_version_string},
        )

    def get_ip(self):
        return "127.0.0.1"


@dataclass
class DOMJudgeServer:
    ip: str
    version: tuple[int, int, int]


@pytest.fixture(scope="module")
def prepare_env(request):
    match request.config.getoption("--integration-backend"):
        case "vagrant":
            env = VagrantEnvironment()
        case "host":
            env = HostEnvironment()
        case _:
            assert False, "Unknown integration backend"

    yield from env.environment()


@pytest.fixture(scope="module", params=[(8, 1, 3), (8, 2, 2), (8, 3, 1), (9, 0, 0)])
def domjudge(request, prepare_env: VagrantEnvironment | HostEnvironment):
    """Returns the IP address of the configured DOMjudge."""

    domjudge_version = request.param
    domjudge_version_string = ".".join(map(str, domjudge_version))

    prepare_env.configure_cgroup(1 if domjudge_version < (9, 0) else 2)
    prepare_env.cleanup_domjudge(domjudge_version_string)
    prepare_env.startup_domjudge(domjudge_version_string)
    yield DOMJudgeServer(ip=prepare_env.get_ip(), version=domjudge_version)


def generate_contest_yaml():
    return textwrap.dedent(f"""
    id:                         tmt-test-{next(_counter)}
    name:                       TMT import test
    start_time:                 2026-01-01T00:00:00+00:00
    duration:                   9999:00:00
    """)


@dataclass
class ExpectedProblemData:
    problem_path: str
    # dict[submission name, result]
    submissions: dict[str, str]
    # set[regex matching some import message]
    scan_messages: set[str] = field(default_factory=set)
    # set[regex not matching any import messages]
    scan_not_messages: set[str] = field(default_factory=set)


# On DOMjudge 8.2, "added" is changed to "added/updated" since the code path shares between adding and inplace update
batch_verdict = ExpectedProblemData(
    problem_path="batch/icpc-verdict",
    submissions={
        "ok.py": "AC",
        "no.cpp": "NO",
        "ok-cpu.cpp": "AC",
        "ok-wall.cpp": "AC",
        "tle-cpu.cpp": "TLE",
        "tle-wall.cpp": "TLE",
        "ok-memory.cpp": "AC",
        "mle.cpp": "RTE",
        "rte.cpp": "RTE",
        "ok-output.cpp": "AC",
        "ole.cpp": "OLE",
    },
    scan_messages={
        r"Added(?:/updated)? 1 sample testcase\(s\): .*",
    },
    scan_not_messages={
        r"Added output validator .*",
    },
)
batch_default_floatcmp = ExpectedProblemData(
    problem_path="batch/icpc-default-floatcmp",
    submissions={
        "model-solution.cpp": "AC",
        "abs1e-4.cpp": "WA",
        "abs1e-6.cpp": "AC",
        "abs1e-7.cpp": "AC",
        "exact.cpp": "AC",
        "no-setprecision.cpp": "WA",
        "rel1e-4.cpp": "WA",
        "rel1e-6.cpp": "AC",
        "rel1e-7.cpp": "AC",
    },
    scan_messages={
        r"Added(?:/updated)? problem statement from: .*",
        r"Added(?:/updated)? 1 secret testcase\(s\): .*",
    },
    scan_not_messages={
        r"Added output validator .*",
    },
)
batch_checker = ExpectedProblemData(
    problem_path="batch/icpc-checker-export",
    submissions={
        "model-solution.cpp": "AC",
        "alt.py": "AC",
        "wrong.cpp": "WA",
    },
    scan_messages={
        r"Added(?:/updated)? problem statement from: .*",
        r"Added(?:/updated)? 1 sample testcase\(s\): .*",
        r"Added(?:/updated)? 1 secret testcase\(s\): .*",
        r"Added output validator .*",
    },
)
interactive_guess = ExpectedProblemData(
    problem_path="interactive/guess",
    submissions={
        "sol.cpp": "AC",
        "brute.cpp": "WA",
        "exit.cpp": "WA",
        "sleep.cpp": "TLE",
        "no-flush.cpp": "TLE",
    },
    scan_messages={
        r"Added(?:/updated)? 3 secret testcase\(s\): .*",
        r"Added output validator .*",
    },
)


@pytest.mark.integration
@pytest.mark.parametrize(
    "problem", [batch_verdict, batch_default_floatcmp, batch_checker, interactive_guess]
)
def test_domjudge_import(domjudge: DOMJudgeServer, problem: ExpectedProblemData):
    import requests

    script_dir = Path(__file__).parent.parent.resolve()
    problem_path = Path(__file__).parent.resolve() / "problems" / problem.problem_path
    formatter = TerminalFormatter()
    context = TMTContext(str(problem_path), str(script_dir))

    # Export a package
    command_clean(formatter=formatter, context=context, skip_confirm=True)
    gen_result = command_gen(
        formatter=formatter, context=context, verify_hash=True, show_reason=False
    )
    assert gen_result
    export_result = command_export(
        formatter=formatter,
        context=context,
        output_path=str(_DOMJUDGE_SCRIPT_PATH / f"{context.config.short_name}.zip"),
        package_format=DOMJudgeLegacyExporter,
        force_output=True,
    )
    assert export_result
    package_path = export_result.exported_path

    try:

        def send(method: str, endpoint: str, files: dict | None = None):
            r = requests.request(
                method,
                f"http://{domjudge.ip}:8888/api/v4/{endpoint}",
                auth=_AUTH,
                files=files,
                headers={"Accept": "application/json"},
            )
            r.raise_for_status()
            return r.json() if r.content else None

        # Upload empty contest and add a problem
        contest_id = send("POST", "contests", {"yaml": generate_contest_yaml()})
        problem_req = send(
            "POST", f"contests/{contest_id}/problems", {"zip": package_path.open("rb")}
        )

        # Check messages
        msgs: list[str]
        if domjudge.version < (8, 2, 0):
            msgs = problem_req["messages"]
        # After DOMjudge 8.2, flatten categorized message lists
        else:
            msgs_dict = cast(dict, problem_req["messages"])
            msgs = sum(msgs_dict.values(), start=[])

        for pattern in problem.scan_messages:
            if not any(re.fullmatch(pattern, msg) for msg in msgs):
                assert False, f"{pattern} did not match any of the messages: {msgs}"

        # Wait for judging
        for _ in range(_JUDGE_TIME_LIMIT_PER_TASK):
            time.sleep(1.0)
            judgement_json = send("GET", f"contests/{contest_id}/judgements")
            if all(j["judgement_type_id"] is not None for j in judgement_json):
                break
        else:
            assert False, f"Judging did not end in {_JUDGE_TIME_LIMIT_PER_TASK} seconds"

        # Check problem metadata
        problem_id = problem_req["problem_id"]
        problem_meta = send("GET", f"contests/{contest_id}/problems/{problem_id}")
        assert isinstance(problem_meta, dict)
        # Available since 8.1
        assert problem_meta.get("short_name") == context.config.short_name
        assert problem_meta.get("time_limit") == context.config.solution.time_limit_sec
        assert problem_meta.get("test_data_count") == len(
            context.recipe.get_all_test_names()
        )

        submission_meta = {}
        for submission in judgement_json:
            submission_id = submission["id"]
            submission_source = send(
                "GET", f"contests/{contest_id}/submissions/{submission_id}/source-code"
            )[0]
            submission_meta[submission_source["filename"]] = submission[
                "judgement_type_id"
            ]
        assert submission_meta == problem.submissions

        # Does not work on DOMjudge 8.3.1, probably related to issue #2210
        # request("DELETE", f"contests/{contest_id}/problems/{problem_id}")
    finally:
        package_path.unlink()
