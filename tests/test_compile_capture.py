import pathlib
import pytest

from internal.formatting import Formatter
from internal.context import TMTContext
from internal.steps.generation import GenerationStep
from internal.commands import command_clean


def test_compile_capture():
    script_dir = pathlib.Path(__file__).parent.parent.resolve()
    problem_dir = pathlib.Path(__file__).parent.resolve() / "bad-generator"
    formatter = Formatter()
    context = TMTContext(str(problem_dir), str(script_dir))

    command_clean(formatter=formatter, context=context, skip_confirm=True)

    generation_step = GenerationStep(context)

    import multiprocessing

    context.config.trusted_compile_time_limit_sec = 10 # overrides
    # run compilation in another thread
    def compile():
        generation_step.prepare_sandbox()
        generation_step.compile()

    p = multiprocessing.Process(target=compile)
    p.start()

    # Wait for 15 seconds or until process finishes
    p.join(15)
    if p.is_alive():
        p.terminate()
        p.join()
        assert False, "Generatior compilation process does not end within target time limit"
        

