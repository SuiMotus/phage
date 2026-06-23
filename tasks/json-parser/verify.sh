#!/bin/bash
set -e
python3 -c "
from solution import parse_json

assert parse_json('null') is None
assert parse_json('true') is True
assert parse_json('false') is False
assert parse_json('42') == 42
assert parse_json('3.14') == 3.14
assert parse_json('\"hello\"') == 'hello'
assert parse_json('\"he\\\"llo\"') == 'he\"llo'
assert parse_json('[1, 2, 3]') == [1, 2, 3]
assert parse_json('[]') == []
assert parse_json('{\"a\": 1}') == {'a': 1}
assert parse_json('{\"a\": [1, {\"b\": true}]}') == {'a': [1, {'b': True}]}
assert parse_json('{}') == {}

# invalid input
try:
    parse_json('{invalid}')
    assert False, 'should have raised'
except ValueError:
    pass

print('all tests passed')
"
