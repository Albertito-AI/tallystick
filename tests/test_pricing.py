"""Numerical invariants, deliberately invalid models, and paper recomputation."""

import importlib.util
import itertools
import math
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tallystick import pricing as p


class ProbabilityTests(unittest.TestCase):
    def test_correlated_pair_and_frechet_limits(self):
        self.assertAlmostEqual(p.joint_probability(0.5, 0.5, 0.3), 0.325)
        self.assertEqual(p.frechet_bounds(0.6, 0.8), (0.3999999999999999, 0.6))
        self.assertEqual(p.joint_probability(0.5, 0.5, -1), 0)
        self.assertEqual(p.joint_probability(0.5, 0.5, 1), 0.5)

    def test_infeasible_correlation_is_rejected_not_clipped(self):
        with self.assertRaises(p.PricingError) as context:
            p.joint_probability(0.1, 0.9, 1)
        self.assertEqual(context.exception.code, "INFEASIBLE_CORRELATION")
        with self.assertRaises(p.PricingError):
            p.joint_probability(0.9, 0.9, -1)

    def test_deterministic_marginals_need_zero_correlation_convention(self):
        self.assertEqual(p.joint_probability(0, 0.7, 0), 0)
        self.assertEqual(p.joint_probability(1, 0.7, 0), 0.7)
        with self.assertRaises(p.PricingError) as context:
            p.joint_probability(1, 0.7, 0.1)
        self.assertEqual(context.exception.code, "UNDEFINED_CORRELATION")

    def test_independence_requires_literal_true(self):
        for opt in (False, None, 1, "true"):
            with self.assertRaises(p.PricingError):
                p.independent_joint_probability([0.5, 0.5], assume_independent=opt)
        self.assertEqual(p.independent_joint_probability([0.5, 0.5], assume_independent=True), 0.25)
        with self.assertRaises(p.PricingError):
            p.independent_combination_hold(0.05, 2)

    def test_decimal_odds_use_expected_hold_convention(self):
        odds = p.decimal_odds(0.4, 0.08)
        self.assertAlmostEqual(odds, 2.3)
        self.assertAlmostEqual(p.expected_return(0.4, odds), -0.08)
        self.assertEqual(p.decimal_odds(1, 0), 1)
        for args in ((0, 0.08), (0.5, 1), (0.9, 0.5), (5e-324, 0)):
            with self.assertRaises(p.PricingError):
                p.decimal_odds(*args)

    def test_combination_hold_and_exact_count(self):
        single_hold = 1 / 22
        self.assertAlmostEqual(p.independent_combination_hold(single_hold, 2, assume_independent=True), 1 - (21 / 22)**2)
        self.assertEqual(p.independent_combination_hold(0, 6, assume_independent=True), 0)
        self.assertEqual(p.independent_combination_hold(1, 6, assume_independent=True), 1)
        self.assertEqual(p.combination_count(50, 6), 1_088_651_720)
        self.assertEqual(p.combination_count(200, 6), 5_356_338_430_880)
        with self.assertRaises(p.PricingError):
            p.combination_count(2, 3)

    def test_poisson_boundaries_and_known_probabilities(self):
        self.assertEqual(p.poisson_tail(0, 0), 1)
        self.assertEqual(p.poisson_tail(0, 1), 0)
        self.assertAlmostEqual(p.poisson_tail(1, 1), 1 - math.exp(-1))
        self.assertAlmostEqual(p.poisson_tail(5.2, 5), 0.5938719984274374, places=14)
        # Direct upper-tail evaluation retains tiny probabilities instead of 1-CDF cancellation.
        self.assertGreater(p.poisson_tail(1, 20), 1e-19)
        self.assertLess(p.poisson_tail(1, 20), 2e-19)
        for args in ((-1, 1), (1001, 5), (1, 10001), (1, 1.5), (True, 5)):
            with self.assertRaises(p.PricingError):
                p.poisson_tail(*args)

    @unittest.skipUnless(importlib.util.find_spec("scipy"), "optional independent SciPy cross-check unavailable")
    def test_poisson_agrees_with_independent_scipy_survival_function(self):
        from scipy.stats import poisson
        for mean in (0.01, 1, 5.2, 50, 700, 1000):
            for threshold in (1, 5, int(mean) + 1, int(mean) + 20):
                got = p.poisson_tail(mean, threshold)
                expected = poisson.sf(threshold - 1, mean)
                self.assertAlmostEqual(got, expected, delta=max(1e-12, expected * 1e-10))

    def test_invalid_numbers_never_produce_numeric_results(self):
        for value in (True, False, "0.5", float("nan"), float("inf"), -0.1, 1.1):
            with self.subTest(value=value), self.assertRaises(p.PricingError):
                p.joint_probability(value, 0.5, 0)
        with self.assertRaises(p.PricingError):
            p.independent_joint_probability([], assume_independent=True)
        with self.assertRaises(p.PricingError):
            p.independent_joint_probability([0.5] * 257, assume_independent=True)
        with self.assertRaises(p.PricingError):
            p.independent_combination_hold(0.1, True, assume_independent=True)

    def test_window_probability_has_time_units(self):
        rate = 3 / (90 * 60)
        self.assertAlmostEqual(p.event_window_probability(rate, 6), 0.003327783945476679)
        self.assertAlmostEqual(p.event_window_probability(rate, 0.5), 0.00027773920110286)
        self.assertEqual(p.event_window_probability(0, 250), 0)
        self.assertEqual(p.event_window_probability(100, 0), 0)
        self.assertEqual(p.event_window_probability(1e12, 1e12), 1)

    def test_base_rates_and_undefined_no_alert_condition(self):
        self.assertAlmostEqual(p.posterior_alert_probability(0.95, 0.99, 0.001), 0.0868372943327238)
        self.assertAlmostEqual(p.posterior_alert_probability(0.95, 0.999, 0.001), 0.48742945100051283)
        with self.assertRaises(p.PricingError):
            p.posterior_alert_probability(0, 1, 0.001)

    def test_deterrence_is_an_explicit_model(self):
        self.assertEqual(p.deterrence_limit(0.1, 1_000_000, 0, 2), 100_000)
        with self.assertRaises(p.PricingError):
            p.deterrence_limit(0.1, 1_000_000, 0, 1)


class LmsrTests(unittest.TestCase):
    def test_initial_prices_and_loss(self):
        self.assertEqual(p.lmsr_prices([0, 0], 1000), [0.5, 0.5])
        self.assertAlmostEqual(p.lmsr_cost([0, 0], 1000), 693.1471805599452)
        self.assertAlmostEqual(p.lmsr_max_loss(1000, 10), 2302.585092994046)
        self.assertAlmostEqual(p.lmsr_prices([300, 0], 1000)[0], 0.574442516811659)

    def test_large_values_do_not_overflow_softmax(self):
        self.assertEqual(p.lmsr_prices([1e12, -1e12], 1e-9), [1, 0])
        self.assertEqual(p.lmsr_cost([1e12, -1e12], 1e-9), 1e12)
        self.assertEqual(p.lmsr_prices([1e12, 1e12], 1), [0.5, 0.5])

    def test_prices_sum_to_one_and_translate_invariantly(self):
        first = p.lmsr_prices([-30, 0, 25], 10)
        second = p.lmsr_prices([70, 100, 125], 10)
        self.assertAlmostEqual(math.fsum(first), 1)
        for x, y in zip(first, second):
            self.assertAlmostEqual(x, y)
        self.assertAlmostEqual(p.lmsr_cost([70, 100, 125], 10) - p.lmsr_cost([-30, 0, 25], 10), 100)

    def test_trade_round_trip_and_path_independence(self):
        a, b, c = [0, 0], [20, 0], [20, 30]
        self.assertAlmostEqual(p.lmsr_trade_cost(a, b, 100) + p.lmsr_trade_cost(b, a, 100), 0)
        self.assertAlmostEqual(p.lmsr_trade_cost(a, b, 100) + p.lmsr_trade_cost(b, c, 100), p.lmsr_trade_cost(a, c, 100))
        self.assertEqual(p.lmsr_trade_cost([1e12, 1e12], [1e12, 1e12], 500), 0)

    def test_subsidy_bound_for_zero_initial_inventory(self):
        final = [10_000, 0]
        cash_in = p.lmsr_trade_cost([0, 0], final, 500)
        worst_loss = max(final) - cash_in
        self.assertLessEqual(worst_loss, p.lmsr_max_loss(500, 2))

    def test_invalid_shapes_and_liquidity(self):
        for qs, b in (([], 1), ([0], 1), ([0, 0], 0), ([0, 0], -1), ([0, float("inf")], 1), ([0, True], 1)):
            with self.assertRaises(p.PricingError):
                p.lmsr_prices(qs, b)
        with self.assertRaises(p.PricingError):
            p.lmsr_trade_cost([0, 0], [0, 0, 0], 1)
        with self.assertRaises(p.PricingError):
            p.lmsr_max_loss(1, True)


class CoherenceTests(unittest.TestCase):
    def test_exhaustive_space_assertion_required(self):
        result = p.coherence_check([[0, 1]], [0.5], [0.5])
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertEqual(result["reason"], "OUTCOME_SPACE_NOT_ASSERTED")

    def test_unavailable_solver_is_unknown(self):
        with patch.object(p.importlib, "import_module", side_effect=ImportError("missing")):
            result = p.coherence_check([[0, 1]], [0.5], [0.5], outcomes_exhaustive=True)
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertEqual(result["reason"], "SOLVER_UNAVAILABLE")

    @unittest.skipUnless(importlib.util.find_spec("scipy"), "optional SciPy solver unavailable")
    def test_feasible_full_space_returns_checked_witness(self):
        result = p.coherence_check([[0, 0, 1, 1], [0, 1, 0, 1], [0, 0, 0, 1]], [0.6, 0.55, 0.4], [0.6, 0.55, 0.4], outcomes_exhaustive=True)
        self.assertEqual(result["status"], "COHERENT")
        self.assertAlmostEqual(sum(result["witness"]), 1)
        self.assertLessEqual(result["max_constraint_violation"], 1e-9)

    @unittest.skipUnless(importlib.util.find_spec("scipy"), "optional SciPy solver unavailable")
    def test_pairwise_valid_but_globally_inconsistent_claims(self):
        states = list(itertools.product((0, 1), repeat=3))
        rows = [[s[i] for s in states] for i in range(3)]
        rows += [[s[i] * s[j] for s in states] for i, j in ((0, 1), (0, 2), (1, 2))]
        values = [0.5, 0.5, 0.5, 0, 0, 0]
        # Each pair permits zero intersection. Three disjoint events cannot each have p=.5.
        self.assertEqual(p.frechet_bounds(0.5, 0.5), (0, 0.5))
        result = p.coherence_check(rows, values, values, outcomes_exhaustive=True)
        self.assertEqual(result["status"], "INCOHERENT")

    def test_bad_solver_witness_never_passes(self):
        fake_result = SimpleNamespace(status=0, success=True, x=[0.5, 0.9])
        fake_scipy = SimpleNamespace(__version__="test")
        fake_solver = SimpleNamespace(linprog=lambda *args, **kwargs: fake_result)
        with patch.object(p.importlib, "import_module", side_effect=[fake_scipy, fake_solver]):
            result = p.coherence_check([[0, 1]], [0.5], [0.5], outcomes_exhaustive=True)
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertEqual(result["reason"], "WITNESS_RESIDUAL_TOO_LARGE")

    def test_timeout_never_passes(self):
        fake_result = SimpleNamespace(status=1, success=False, x=None)
        with patch.object(p.importlib, "import_module", side_effect=[SimpleNamespace(__version__="test"), SimpleNamespace(linprog=lambda *a, **k: fake_result)]):
            result = p.coherence_check([[0, 1]], [0.5], [0.5], outcomes_exhaustive=True)
        self.assertEqual(result["status"], "UNKNOWN")

    def test_invalid_matrices_rejected(self):
        for rows, lower, upper in (([], [], []), ([[0, 1], [1]], [0, 0], [1, 1]), ([[0, 2]], [0], [1]), ([[0, 1]], [0.8], [0.2]), ([[False, True]], [0], [1])):
            with self.assertRaises(p.PricingError):
                p.coherence_check(rows, lower, upper, outcomes_exhaustive=True)
        with self.assertRaises(p.PricingError):
            p.coherence_check([[0, 1]], [0.5], [0.5], outcomes_exhaustive="true")


class SimulationTests(unittest.TestCase):
    def test_reproducible_estimate_and_explicit_error_budget(self):
        first = p.simulate_joint([0.2, 0.3, 0.1, 0.4], [3], samples=20_000, seed=42)
        second = p.simulate_joint([0.2, 0.3, 0.1, 0.4], [3], samples=20_000, seed=42)
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "WITHIN_ERROR_BUDGET")
        self.assertEqual(first["model_probability"], 0.4)
        self.assertLess(first["sampling_error_bound"], 0.01)
        self.assertAlmostEqual(first["sampling_error_bound"], math.sqrt(math.log(40) / 40000))
        rejected = p.simulate_joint([0.2, 0.8], [1], samples=100, max_error=0.01)
        self.assertEqual(rejected["status"], "REJECTED_ERROR_BUDGET")

    def test_zero_probability_categories_never_selected(self):
        self.assertEqual(p.simulate_joint([0, 1, 0], [0, 2], samples=100)["estimate"], 0)
        self.assertEqual(p.simulate_joint([0, 1, 0], [1], samples=100)["estimate"], 1)
        self.assertEqual(p.simulate_joint([0, 1, 0], [], samples=100)["estimate"], 0)

    def test_unbounded_or_malformed_simulations_rejected(self):
        for distribution, success, kwargs in (([0.2, 0.2], [0], {}), ([0.5, 0.5], [2], {}), ([0.5, 0.5], [0, 0], {}), ([0.5, 0.5], [0], {"samples": 1_000_001}), ([0.5, 0.5], [0], {"samples": True}), ([0.5, 0.5], [0], {"confidence": 1}), ([0.5, 0.5], [0], {"seed": -1}), ([0.5, 0.5], [0], {"max_error": 0})):
            with self.subTest(kwargs=kwargs), self.assertRaises(p.PricingError):
                p.simulate_joint(distribution, success, **kwargs)

    def test_appendix_a_recomputed(self):
        result = p.whitepaper_example()
        self.assertAlmostEqual(result["joint_probability"], 0.36327814537918757, places=14)
        self.assertAlmostEqual(result["correlated_decimal_odds"], 2.532494761113993, places=13)
        self.assertAlmostEqual(result["independent_decimal_odds"], 2.8166461411829906, places=13)
        self.assertAlmostEqual(result["expected_return_if_independence_quote"], 0.023225986358402118, places=13)
        self.assertAlmostEqual(result["lmsr_max_loss"], 346.5735902799726)
        self.assertEqual(result["status"], "ILLUSTRATIVE_MODEL_ONLY")


if __name__ == "__main__":
    unittest.main()
