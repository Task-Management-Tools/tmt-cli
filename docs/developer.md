## Developer Guide

Other sections TBA.

### Tests

TMT utilizes [pytest](https://docs.pytest.org/en/stable/) as the main testing framework.
The basic set of tests can be run via `python -m pytest` on the root of the repository.

In addition, there are integration tests, which will not be run by default.
To run them, specify the flag `--run-integration` to run them.
On your machine, you should never use ``--integration-backend=host`. This option assumes the host is a clean machine that it can operate on (usually on CI).

#### DOMjudge Integration Test

The file `tests/test_domjudge_export.py` and `tests/domjudge` is the testing tool for DOMjudge integration tests.
Currently, the test spins up a Vagrant VM and installs DOMjudge, then check if the exported package can be imported and correctly run in DOMjudge.

Running the test requires Vagrant and libvirt installed on the host machine.
