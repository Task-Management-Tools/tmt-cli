from pathlib import Path
from dataclasses import dataclass
import os
import shutil
import subprocess
import itertools
import time
import textwrap

import pytest

from internal.commands import command_clean, command_export, command_gen
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
def prepare_domjudge(request, prepare_env: VagrantEnvironment | HostEnvironment):
    """Returns the IP address of the configured DOMjudge."""

    domjudge_version = request.param
    domjudge_version_string = ".".join(map(str, domjudge_version))

    prepare_env.configure_cgroup(1 if domjudge_version < (9, 0) else 2)
    prepare_env.cleanup_domjudge(domjudge_version_string)
    prepare_env.startup_domjudge(domjudge_version_string)
    yield prepare_env.get_ip()


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
    submissions: dict[str, str]


icpc_default_floatcmp = ExpectedProblemData(
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
)


@pytest.mark.integration
@pytest.mark.parametrize("problem", [icpc_default_floatcmp])
def test_domjudge_export(prepare_domjudge: str, problem: ExpectedProblemData):
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
        vm_ip = prepare_domjudge
        # input("Is DOMjudge on? [y/n]")

        def request(method: str, endpoint: str, files: dict = None):
            r = requests.request(
                method,
                f"http://{vm_ip}:8888/api/v4/{endpoint}",
                auth=_AUTH,
                files=files,
                headers={"Accept": "application/json"},
            )
            r.raise_for_status()
            return r.json() if r.content else None

        contest_id = request("POST", "contests", {"yaml": generate_contest_yaml()})
        problem_req = request(
            "POST", f"contests/{contest_id}/problems", {"zip": package_path.open("rb")}
        )

        print(problem_req["messages"])
        problem_id = problem_req["problem_id"]

        for _ in range(_JUDGE_TIME_LIMIT_PER_TASK):
            time.sleep(1.0)
            judgement_json = request("GET", f"contests/{contest_id}/judgements")
            if all(j["judgement_type_id"] is not None for j in judgement_json):
                print(judgement_json)
                break
        else:
            assert False, f"Judging did not end in {_JUDGE_TIME_LIMIT_PER_TASK} seconds"

        problem_meta = request("GET", f"contests/{contest_id}/problems/{problem_id}")
        print(problem_meta)
        # Available since 8.1
        assert problem_meta.get("short_name") == context.config.short_name
        assert problem_meta.get("time_limit") == context.config.solution.time_limit_sec
        assert problem_meta.get("test_data_count") == len(
            context.recipe.get_all_test_names()
        )

        submission_meta = {}
        for submission in judgement_json:
            submission_id = submission["id"]
            submission_source = request(
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
