import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("calculation", Path(__file__).parents[1] / "custom_components/indoor_aqi/calculation.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


class CalculationTests(unittest.TestCase):
    def test_all_breakpoints(self):
        for low, high, ilow, ihigh in c.BREAKPOINTS:
            with self.subTest(low=low, high=high):
                self.assertEqual(c.calculate(str(low / 10)), ilow)
                self.assertEqual(c.calculate(str(high / 10)), ihigh)

    def test_sample_values(self):
        self.assertEqual([c.calculate(p) for p in [8, 10, 11, 4]], [44, 53, 55, 22])
        self.assertEqual(c.summarize([44, 53, 55, 22]), (44, 55))

    def test_truncation_and_rounding(self):
        self.assertEqual(c.calculate("9.0999999"), 50)
        self.assertEqual(c.calculate("9.1"), 51)
        self.assertEqual(c.calculate("35.49"), 100)
        self.assertEqual(c.calculate("35.5"), 101)
        self.assertEqual(c.calculate("0.09"), 0)
        self.assertEqual(c.calculate("0.1"), 1)

    def test_invalid(self):
        for value in (None, "unknown", "unavailable", "", "NaN", "Infinity",
                      "-Infinity", -0.1, True, False, {}, "garbage"):
            with self.subTest(value=value):
                self.assertIsNone(c.calculate(value))

    def test_cap(self):
        self.assertEqual(c.calculate("325.4"), 500)
        self.assertEqual(c.calculate("9999999999999"), 500)

    def test_monotonic_every_tenth(self):
        values = [c.calculate(str(i / 10)) for i in range(4001)]
        self.assertEqual(values, sorted(values))
        self.assertTrue(all(0 <= x <= 500 for x in values))

    def test_valid_only_summary(self):
        self.assertEqual(c.summarize([None, 0, 50]), (25, 50))
        self.assertEqual(c.summarize([None, None]), (None, None))
        self.assertEqual(c.summarize([]), (None, None))
        self.assertEqual(c.summarize([2, 3]), (3, 3))

    def test_unit_and_device_class(self):
        for unit in c.UNITS:
            self.assertTrue(c.is_pm25("pm25", unit))
        self.assertFalse(c.is_pm25("pm10", "µg/m³"))
        self.assertFalse(c.is_pm25("pm25", "mg/m³"))
        self.assertFalse(c.is_pm25("aqi", "µg/m³"))
        self.assertFalse(c.is_pm25("pm25", None))

    def test_categories(self):
        for v, label in [(0,"good"),(50,"good"),(51,"moderate"),(100,"moderate"),
                         (101,"unhealthy_sensitive"),(150,"unhealthy_sensitive"),
                         (151,"unhealthy"),(200,"unhealthy"),(201,"very_unhealthy"),
                         (300,"very_unhealthy"),(301,"hazardous"),(500,"hazardous")]:
            self.assertEqual(c.category(v), label)
        self.assertIsNone(c.category(None))
