import math


def parse_pall(val) -> float:
    """Parse a pallet value (possibly using comma as decimal separator) to float."""
    try:
        return float(str(val).replace(",", "."))
    except (ValueError, TypeError):
        return 0.0


def calc_pall(weight_kg: float, baseline: float) -> str:
    """Round weight/baseline up to nearest 0.5, formatted with comma decimal."""
    try:
        raw = float(weight_kg) / baseline
        rounded = math.ceil(raw * 2) / 2
        if rounded == int(rounded):
            return str(int(rounded))
        return str(rounded).replace(".", ",")
    except (TypeError, ValueError, ZeroDivisionError):
        return "0"
