#!/bin/bash
set -e
result=$(python3 solve.py)
expected="645.5"
if [ "$result" = "$expected" ]; then
  exit 0
else
  echo "expected $expected, got $result"
  exit 1
fi
