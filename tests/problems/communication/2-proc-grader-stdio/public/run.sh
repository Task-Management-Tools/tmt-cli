#!/bin/bash

task="{config.short_name}"
memory={config.solution.memory_limit_kib}  # {config.solution.memory_limit_gib:.4g}GB
stack_size={config.solution.memory_limit_kib}  # {config.solution.memory_limit_gib:.4g}GB

ulimit -v "${memory}"
ulimit -s "${stack_size}"
"./${task}"
