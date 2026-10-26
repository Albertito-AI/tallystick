"""Bounded numerical experiments for Tallystick's research sandbox.

Inputs are supplied model assumptions, never observations of market truth.
Only ``coherence_check`` optionally imports SciPy. No function performs I/O,
places an order, changes a balance, or fits a forecasting model.
"""

from __future__ import annotations

import importlib
import math
import random
from bisect import bisect_right
from numbers import Real
from typing import Any, Sequence

MAX_OUTCOMES = 256
MAX_MARKETS = 64
MAX_SAMPLES = 1_000_000
MAX_MAGNITUDE = 1e12
LP_TOLERANCE = 1e-9


class PricingError(ValueError):
    """Invalid or unsupported model input, with a machine-readable reason."""

    def __init__(self, message: str, code: str = "INVALID_PRICING_INPUT") -> None:
        super().__init__(message)
        self.code = code


def _number(value: Any, name: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise PricingError(f"{name} must be a finite number")
    try:
        result = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise PricingError(f"{name} must be a finite number") from exc
    if not math.isfinite(result) or not low <= result <= high:
        raise PricingError(f"{name} must be between {low} and {high}")
    return result


def _integer(value: Any, name: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise PricingError(f"{name} must be an integer between {low} and {high}")
    return value


def _probability(value: Any, name: str) -> float:
    return _number(value, name, 0.0, 1.0)


def _sequence(value: Any, name: str, low: int, high: int) -> list[Any]:
    if not isinstance(value, (list, tuple)) or not low <= len(value) <= high:
        raise PricingError(f"{name} must contain between {low} and {high} values")
    return list(value)


def frechet_bounds(p_a: float, p_b: float) -> tuple[float, float]:
    """Necessary and sufficient bounds on one pair's intersection probability."""
    a, b = _probability(p_a, "p_a"), _probability(p_b, "p_b")
    return max(0.0, a + b - 1.0), min(a, b)


def joint_probability(p_a: float, p_b: float, rho: float) -> float:
    """Intersection probability from a supplied Bernoulli correlation.

The feasible range of rho depends on the marginals. An infeasible result is
rejected, never clipped into that range. A zero-variance event accepts rho=0
as an explicit convention and rejects nonzero, undefined correlations.
"""
    a, b = _probability(p_a, "p_a"), _probability(p_b, "p_b")
    correlation = _number(rho, "rho", -1.0, 1.0)
    scale = math.sqrt(a * (1.0 - a) * b * (1.0 - b))
    if scale == 0.0 and correlation != 0.0:
        raise PricingError("Correlation is undefined for a deterministic event", "UNDEFINED_CORRELATION")
    result = a * b + correlation * scale
    lower, upper = frechet_bounds(a, b)
    if not lower <= result <= upper:
        raise PricingError("Correlation is incompatible with the supplied marginals", "INFEASIBLE_CORRELATION")
    return result


def independent_joint_probability(
    probabilities: Sequence[float], *, assume_independent: bool = False
) -> float:
    """Product probability only after an explicit independence assumption."""
    values = _sequence(probabilities, "probabilities", 1, MAX_OUTCOMES)
    if assume_independent is not True:
        raise PricingError("Independence must be explicitly assumed", "INDEPENDENCE_NOT_ASSUMED")
    return math.prod(_probability(p, f"probabilities[{i}]") for i, p in enumerate(values))


def decimal_odds(probability: float, hold: float = 0.0) -> float:
    """Return (1-hold)/p, where hold is expected revenue per unit stake.

This is an expected-hold convention, not the overround of a full price set.
Impossible events and a gross payout below the original stake are rejected.
"""
    p, h = _probability(probability, "probability"), _probability(hold, "hold")
    if p == 0 or h == 1:
        raise PricingError("A quote requires p>0 and hold<1", "UNQUOTABLE_PROBABILITY")
    result = (1.0 - h) / p
    if not math.isfinite(result) or not 1.0 <= result <= MAX_MAGNITUDE:
        raise PricingError("Decimal odds must be between 1 and 1e12", "UNQUOTABLE_PROBABILITY")
    return result


def expected_return(probability: float, odds: float) -> float:
    """Expected net return per unit stake under the supplied probability."""
    return _probability(probability, "probability") * _number(odds, "odds", 1.0, MAX_MAGNITUDE) - 1.0


def independent_combination_hold(
    hold: float, legs: int, *, assume_independent: bool = False
) -> float:
    """Expected hold for equally margined, explicitly independent legs."""
    h = _probability(hold, "hold")
    n = _integer(legs, "legs", 1, MAX_OUTCOMES)
    if assume_independent is not True:
        raise PricingError("Independence must be explicitly assumed", "INDEPENDENCE_NOT_ASSUMED")
    return 1.0 if h == 1.0 else -math.expm1(n * math.log1p(-h))


def combination_count(markets: int, max_legs: int) -> int:
    """Count selections of one outcome in each selected binary market."""
    k = _integer(markets, "markets", 1, 10_000)
    limit = _integer(max_legs, "max_legs", 1, min(k, MAX_OUTCOMES))
    return sum(math.comb(k, n) * 2**n for n in range(1, limit + 1))


def poisson_tail(mean: float, threshold: int) -> float:
    """P[X>=threshold] for a supplied Poisson mean, using bounded recurrence.

Compute the smaller tail directly to avoid cancellation when the requested
upper tail is tiny. This float implementation supports mean<=1000 and
threshold<=10000. It is a model calculation, not a fitted sports forecast.
"""
    mu = _number(mean, "mean", 0.0, 1000.0)
    k = _integer(threshold, "threshold", 0, 10_000)
    if k == 0:
        return 1.0
    if mu == 0.0:
        return 0.0
    if k <= mu:
        index = k - 1
        term = math.exp(index * math.log(mu) - mu - math.lgamma(index + 1))
        terms = [term]
        while index:
            term *= index / mu
            terms.append(term)
            index -= 1
        return 1.0 - math.fsum(terms)
    term = math.exp(k * math.log(mu) - mu - math.lgamma(k + 1))
    terms = [term]
    total = term
    for index in range(k + 1, k + 10_001):
        term *= mu / index
        terms.append(term)
        total += term
        if term == 0.0 or term < total * 1e-16:
            return math.fsum(terms)
    raise PricingError("Poisson recurrence did not converge within its bound", "NUMERICAL_LIMIT")


def _lmsr_inputs(quantities: Sequence[float], b: float) -> tuple[list[float], float]:
    values = _sequence(quantities, "quantities", 2, MAX_OUTCOMES)
    qs = [_number(q, f"quantities[{i}]", -MAX_MAGNITUDE, MAX_MAGNITUDE) for i, q in enumerate(values)]
    liquidity = _number(b, "b", 1e-9, MAX_MAGNITUDE)
    return qs, liquidity


def _shifted_lse(qs: list[float], liquidity: float) -> tuple[float, float]:
    maximum = max(qs)
    return maximum, math.log(math.fsum(math.exp((q - maximum) / liquidity) for q in qs))


def lmsr_cost(quantities: Sequence[float], b: float) -> float:
    """Stable LMSR cost, for mutually exclusive exhaustive unit-payoff outcomes."""
    qs, liquidity = _lmsr_inputs(quantities, b)
    maximum, log_sum = _shifted_lse(qs, liquidity)
    return maximum + liquidity * log_sum


def lmsr_prices(quantities: Sequence[float], b: float) -> list[float]:
    """LMSR softmax prices. Extreme floats may underflow to zero."""
    qs, liquidity = _lmsr_inputs(quantities, b)
    maximum = max(qs)
    weights = [math.exp((q - maximum) / liquidity) for q in qs]
    total = math.fsum(weights)
    return [w / total for w in weights]


def lmsr_trade_cost(before: Sequence[float], after: Sequence[float], b: float) -> float:
    """C(after)-C(before), subtracting shifted expressions to reduce cancellation."""
    old, liquidity = _lmsr_inputs(before, b)
    new, _ = _lmsr_inputs(after, b)
    if len(old) != len(new):
        raise PricingError("The before and after outcome dimensions must match")
    old_max, old_lse = _shifted_lse(old, liquidity)
    new_max, new_lse = _shifted_lse(new, liquidity)
    return (new_max - old_max) + liquidity * (new_lse - old_lse)


def lmsr_max_loss(b: float, outcomes: int) -> float:
    """b*log(n), for fixed b and an initially uniform zero-inventory LMSR."""
    liquidity = _number(b, "b", 1e-9, MAX_MAGNITUDE)
    n = _integer(outcomes, "outcomes", 2, MAX_OUTCOMES)
    return liquidity * math.log(n)


def event_window_probability(rate_per_second: float, seconds: float) -> float:
    """At least one event in a homogeneous Poisson process over the window."""
    rate = _number(rate_per_second, "rate_per_second", 0.0, MAX_MAGNITUDE)
    duration = _number(seconds, "seconds", 0.0, MAX_MAGNITUDE)
    return -math.expm1(-rate * duration)


def posterior_alert_probability(sensitivity: float, specificity: float, base_rate: float) -> float:
    """Positive predictive value under the supplied detection assumptions."""
    s, t, theta = (_probability(v, n) for v, n in (
        (sensitivity, "sensitivity"), (specificity, "specificity"), (base_rate, "base_rate")
    ))
    positive = s * theta
    total = positive + (1.0 - t) * (1.0 - theta)
    if total == 0.0:
        raise PricingError("Conditional probability is undefined when no alerts can occur", "UNDEFINED_CONDITIONAL")
    return positive / total


def deterrence_limit(detection_probability: float, sanction: float, direct_cost: float, odds: float) -> float:
    """Illustrative risk-neutral model (p*F+c)/(o-1), not an operational cap."""
    p = _probability(detection_probability, "detection_probability")
    fine = _number(sanction, "sanction", 0.0, MAX_MAGNITUDE)
    cost = _number(direct_cost, "direct_cost", 0.0, MAX_MAGNITUDE)
    price = _number(odds, "odds", 1.0, MAX_MAGNITUDE)
    if price == 1.0:
        raise PricingError("The illustrative deterrence formula requires odds>1")
    result = (p * fine + cost) / (price - 1.0)
    if not math.isfinite(result) or result > MAX_MAGNITUDE:
        raise PricingError("The illustrative deterrence result exceeds its supported bound", "NUMERICAL_LIMIT")
    return result


def coherence_check(
    payoffs: Sequence[Sequence[int]],
    lower: Sequence[float],
    upper: Sequence[float],
    *,
    outcomes_exhaustive: bool = False,
) -> dict[str, Any]:
    """Test finite-outcome linear feasibility using optional SciPy/HiGHS.

Rows are binary claim payoffs; columns must enumerate every possible joint
outcome. The caller must expressly assert exhaustiveness. This is bounded
floating-point feasibility with a checked residual, not a formal certificate.
"""
    rows = _sequence(payoffs, "payoffs", 1, MAX_MARKETS)
    matrix = [_sequence(row, f"payoffs[{i}]", 1, MAX_OUTCOMES) for i, row in enumerate(rows)]
    width = len(matrix[0])
    if any(len(row) != width for row in matrix):
        raise PricingError("All payoff rows must have the same outcome count")
    if any(type(value) is not int or value not in (0, 1) for row in matrix for value in row):
        raise PricingError("Payoffs must be integer 0 or 1")
    lows = [_probability(v, f"lower[{i}]") for i, v in enumerate(_sequence(lower, "lower", len(rows), len(rows)))]
    highs = [_probability(v, f"upper[{i}]") for i, v in enumerate(_sequence(upper, "upper", len(rows), len(rows)))]
    if any(lo > hi for lo, hi in zip(lows, highs)):
        raise PricingError("Each lower bound must be at most its upper bound")
    if type(outcomes_exhaustive) is not bool:
        raise PricingError("outcomes_exhaustive must be boolean")
    result: dict[str, Any] = {
        "status": "UNKNOWN", "outcome_count": width, "market_count": len(rows),
        "witness": None, "scope": "supplied finite outcome space",
        "tolerance": LP_TOLERANCE, "outcomes_exhaustive_asserted": outcomes_exhaustive,
    }
    if not outcomes_exhaustive:
        return {**result, "reason": "OUTCOME_SPACE_NOT_ASSERTED"}
    try:
        scipy = importlib.import_module("scipy")
        linprog = importlib.import_module("scipy.optimize").linprog
    except ImportError:
        return {**result, "reason": "SOLVER_UNAVAILABLE"}
    try:
        solved = linprog(
            [0.0] * width,
            A_ub=matrix + [[-x for x in row] for row in matrix],
            b_ub=highs + [-x for x in lows], A_eq=[[1.0] * width], b_eq=[1.0],
            bounds=[(0.0, 1.0)] * width, method="highs",
            options={"time_limit": 2.0, "maxiter": 10_000,
                     "primal_feasibility_tolerance": LP_TOLERANCE,
                     "dual_feasibility_tolerance": LP_TOLERANCE},
        )
    except Exception as exc:
        # Backend failure never falls through to a favourable decision.
        return {**result, "reason": "SOLVER_ERROR", "error_type": type(exc).__name__}
    result.update({"solver": "scipy.optimize.linprog/highs", "solver_version": scipy.__version__,
                   "solver_status": int(solved.status)})
    if solved.status == 2:
        return {**result, "status": "INCOHERENT", "reason": "SOLVER_INFEASIBLE"}
    if not solved.success or solved.x is None:
        return {**result, "reason": "SOLVER_INCONCLUSIVE"}
    witness = [float(x) for x in solved.x]
    if len(witness) != width or any(not math.isfinite(x) for x in witness):
        return {**result, "reason": "INVALID_SOLVER_WITNESS"}
    prices = [math.fsum(a * p for a, p in zip(row, witness)) for row in matrix]
    violation = max([abs(math.fsum(witness) - 1.0)] +
                    [max(0.0, -x, x - 1.0) for x in witness] +
                    [max(0.0, lo - price, price - hi) for lo, hi, price in zip(lows, highs, prices)])
    if violation > LP_TOLERANCE:
        return {**result, "reason": "WITNESS_RESIDUAL_TOO_LARGE", "max_constraint_violation": violation}
    return {**result, "status": "COHERENT", "reason": "NUMERICALLY_FEASIBLE",
            "witness": witness, "implied_prices": prices, "max_constraint_violation": violation}


def simulate_joint(
    distribution: Sequence[float],
    success_outcomes: Sequence[int],
    *,
    samples: int = 20_000,
    seed: int = 0,
    max_error: float = 0.01,
    confidence: float = 0.95,
) -> dict[str, Any]:
    """Reproducible Monte Carlo over a supplied complete joint distribution.

The error budget is a two-sided Hoeffding sampling bound conditional on IID
draws from that model. It says nothing about the model's real-world accuracy.
The finite model's exact probability is also returned so this demonstration
can be inspected. It does not infer correlations from marginal prices.
"""
    weights = [_probability(v, f"distribution[{i}]") for i, v in enumerate(
        _sequence(distribution, "distribution", 1, MAX_OUTCOMES))]
    total = math.fsum(weights)
    if abs(total - 1.0) > 1e-12:
        raise PricingError("Joint distribution must sum to 1 within 1e-12")
    selected = _sequence(success_outcomes, "success_outcomes", 0, len(weights))
    success = {_integer(i, "success outcome", 0, len(weights) - 1) for i in selected}
    if len(success) != len(selected):
        raise PricingError("Success outcome indices must be distinct")
    count = _integer(samples, "samples", 1, MAX_SAMPLES)
    rng_seed = _integer(seed, "seed", 0, 2**63 - 1)
    error_budget = _number(max_error, "max_error", 1e-9, 1.0)
    certainty = _number(confidence, "confidence", 1e-9, 1.0 - 1e-12)
    normalized = [p / total for p in weights]
    cumulative = [math.fsum(normalized[:i + 1]) for i in range(len(weights))]
    cumulative[-1] = 1.0  # Final roundoff correction after disclosed normalization.
    rng = random.Random(rng_seed)
    successes = sum(bisect_right(cumulative, rng.random()) in success for _ in range(count))
    estimate = successes / count
    bound = math.sqrt(math.log(2.0 / (1.0 - certainty)) / (2.0 * count))
    return {
        "status": "WITHIN_ERROR_BUDGET" if bound <= error_budget else "REJECTED_ERROR_BUDGET",
        "estimate": estimate, "samples": count, "seed": rng_seed,
        "confidence": certainty, "sampling_error_bound": bound, "max_error": error_budget,
        "interval": [max(0.0, estimate - bound), min(1.0, estimate + bound)],
        "model_probability": math.fsum(normalized[i] for i in success),
        "input_distribution_sum": total, "roundoff_normalization": total != 1.0,
        "method": "seeded finite-model sampling with two-sided Hoeffding bound",
        "scope": "conditional sampling error; model error and calibration are unmeasured",
    }


def whitepaper_example() -> dict[str, Any]:
    """Recompute Appendix A without fitting or claiming a real sports model."""
    corners = poisson_tail(5.2, 5)
    goals, rho, hold = 0.55, 0.15, 0.08
    joint = joint_probability(corners, goals, rho)
    independent = independent_joint_probability([corners, goals], assume_independent=True)
    independent_quote = decimal_odds(independent, hold)
    return {
        "status": "ILLUSTRATIVE_MODEL_ONLY", "corners_poisson_mean": 5.2,
        "corners_threshold": 5, "corners_probability": corners,
        "goals_probability": goals, "correlation": rho,
        "joint_probability": joint, "frechet_bounds": list(frechet_bounds(corners, goals)),
        "independent_joint_probability": independent, "expected_hold": hold,
        "correlated_decimal_odds": decimal_odds(joint, hold),
        "independent_decimal_odds": independent_quote,
        "expected_return_if_independence_quote": expected_return(joint, independent_quote),
        "lmsr_b": 500, "lmsr_outcomes": 2, "lmsr_max_loss": lmsr_max_loss(500, 2),
        "assumptions": ["supplied Poisson model", "supplied Bernoulli correlation",
                        "expected-hold price convention", "no fitted or validated live model"],
    }
