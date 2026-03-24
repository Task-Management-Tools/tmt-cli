#!/bin/bash

task="{config.short_name}"
grader_name="grader"

g++ -std=gnu++20 -Wall -O2 -pipe -static -g -o "${task}" "${grader_name}.cpp" "${task}.cpp"
