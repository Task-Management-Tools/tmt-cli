#!/bin/bash

task="{config.short_name}"
grader_name="{config.solution.grader_name}"

g++ -std=gnu++20 -Wall -O2 -pipe -static -g -o "${task}" "${grader_name}.cpp" "${task}.cpp"
