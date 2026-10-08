"""Test suite for math_service."""

import pytest
from math_service import safe_divide, calculate_percentage_discount, compute_median


def test_safe_divide():
    assert safe_divide(10, 2) == 5.0
    assert safe_divide(7, 2) == 3.5

    # Division by zero should safely raise ValueError
    with pytest.raises(ValueError):
        safe_divide(10, 0)


def test_calculate_percentage_discount():
    assert calculate_percentage_discount(100.0, 20.0) == 80.0
    assert calculate_percentage_discount(50.0, 50.0) == 25.0
    assert calculate_percentage_discount(200.0, 0.0) == 200.0

    with pytest.raises(ValueError):
        calculate_percentage_discount(100.0, -5.0)


def test_compute_median():
    # Odd count sorted
    assert compute_median([1, 3, 5]) == 3.0

    # Unsorted odd count
    assert compute_median([5, 1, 3]) == 3.0

    # Unsorted even count
    assert compute_median([10, 2, 8, 4]) == 6.0

    with pytest.raises(ValueError):
        compute_median([])
