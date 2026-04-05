from .base import Formatter


class EmptyFormatter(Formatter):
    def __init__(self):
        super().__init__()

    def print(self, *args, endl=False) -> None:
        pass

    def print_fixed_width(self, *args, width: int, endl=False) -> None:
        pass

    def print_compile_result(self, result, name: str = "", endl: bool = True) -> None:
        pass

    def print_exec_result(self, result) -> None:
        pass

    def print_checker_reason(self, reason: str) -> None:
        pass

    def print_checker_status(self, result) -> None:
        pass

    def print_exec_details(self, result, context) -> None:
        pass

    def print_testcase_verdict(
        self, result, context, print_reason: bool = False
    ) -> None:
        pass

    def print_testset_summary(self, results, overall, context) -> None:
        pass

    def print_hash_diff(self, official_testcase_hashes, testcase_hashes) -> None:
        pass
