"""EPA 2024 PM2.5 breakpoint conversion for instantaneous indoor readings."""
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_UP, localcontext

# Tenths of micrograms per cubic metre, integer arithmetic for boundaries.
BREAKPOINTS = (
    (0, 90, 0, 50),
    (91, 354, 51, 100),
    (355, 554, 101, 150),
    (555, 1254, 151, 200),
    (1255, 2254, 201, 300),
    (2255, 3254, 301, 500),
)
UNITS = frozenset(("µg/m³", "μg/m³", "ug/m³", "µg/m3", "μg/m3", "ug/m3"))


def is_pm25(device_class, unit):
    return device_class == "pm25" and unit in UNITS


def calculate(value):
    """Return rounded index, or None for invalid data; display capped at 500."""
    if isinstance(value, bool):
        return None
    try:
        p = Decimal(str(value))
        if not p.is_finite() or p < 0:
            return None
        if p >= Decimal("325.4"):
            return 500
        with localcontext() as ctx:
            ctx.prec = 40
            n = int((p * 10).to_integral_value(rounding=ROUND_DOWN))
        for low, high, ilow, ihigh in BREAKPOINTS:
            if low <= n <= high:
                # Half-up rounding of the exact rational expression.
                den = high - low
                num = ilow * den + (n - low) * (ihigh - ilow)
                return (2 * num + den) // (2 * den)
    except (InvalidOperation, ValueError, TypeError, OverflowError):
        return None
    return None


def summarize(values):
    """Arithmetic mean of valid source indices, and maximum; no false zero."""
    valid = [v for v in values if v is not None]
    if not valid:
        return None, None
    total = sum(valid)
    return (2 * total + len(valid)) // (2 * len(valid)), max(valid)


def category(value):
    if value is None:
        return None
    for limit, label in ((50, "good"), (100, "moderate"),
                         (150, "unhealthy_sensitive"), (200, "unhealthy"),
                         (300, "very_unhealthy"), (500, "hazardous")):
        if value <= limit:
            return label
    return "hazardous"
