#!/bin/bash
set -e
python3 -c "
from solution import binary_search

assert binary_search([], 5) == -1
assert binary_search([1], 1) == 0
assert binary_search([1], 2) == -1
assert binary_search([1,2,3,4,5], 3) == 2
assert binary_search([1,2,3,4,5], 1) == 0
assert binary_search([1,2,3,4,5], 5) == 4
assert binary_search([1,2,3,4,5], 0) == -1
assert binary_search([1,2,3,4,5], 6) == -1
assert binary_search([1,1,1,2,3], 1) == 0
assert binary_search([1,2,2,2,3], 2) == 1
assert binary_search(list(range(10000)), 9999) == 9999
print('all tests passed')
"
