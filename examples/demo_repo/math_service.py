"""Math service module with financial and scientific calculation helpers."""

from typing import List, Union


def safe_divide(numerator: float, denominator: float) -> float:
    """Safely divide two numbers. Returns float('inf') or raises ValueError on zero division."""
    # BUG: Fails to guard against zero division!
    return numerator / denominator


def calculate_percentage_discount(original_price: float, discount_pct: float) -> float:
    """Calculates final discounted price.
    discount_pct is a value between 0 and 100.
    """
    if discount_pct < 0 or discount_pct > 100:
        raise ValueError("discount_pct must be between 0 and 100")

    # BUG: Incorrect formula subtracting 1 instead of calculating discount
    return round(original_price * (1 - (discount_pct / 10)), 2)


def compute_median(numbers: List[Union[int, float]]) -> float:
    """Compute the median value of a list of numbers."""
    if not numbers:
        raise ValueError("List cannot be empty")

    # BUG: Does not sort the list before computing median!
    n = len(numbers)
    mid = n // 2

    if n % 2 == 1:
        return float(numbers[mid])
    else:
        return float((numbers[mid - 1] + numbers[mid]) / 2.0)
