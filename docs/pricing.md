# Pricing experiments and numerical limits

The pricing module reproduces the foundational paper's illustrative calculations and provides bounded numerical checks. Every probability, correlation and distribution is supplied by the caller. This version does not estimate a sports model, obtain licensed live odds, place bets or operate a market maker. A passing numerical check establishes only the stated mathematical condition under the supplied assumptions.

The implementation is `src/tallystick/pricing.py`. It uses the Python standard library. The finite-outcome coherence check optionally loads SciPy; its absence produces `UNKNOWN`, while the remaining functions continue to work. The optional solver is separate from the basic replay and settlement workflow.

## Pairwise probabilities and independence

For Bernoulli indicators with marginal probabilities `p_a`, `p_b` and supplied correlation `rho`, the intersection probability is

```text
p_a*p_b + rho*sqrt(p_a*(1-p_a)*p_b*(1-p_b))
```

The feasible intersection range is `[max(0, p_a+p_b-1), min(p_a,p_b)]`. A correlation between minus one and one can still be incompatible with the marginals. `joint_probability` rejects that input with `INFEASIBLE_CORRELATION`; it does not adjust the proposed model by clipping its answer. For a deterministic marginal, correlation is undefined. This API accepts `rho=0` as an explicit convention yielding the uniquely determined intersection, and rejects any other supplied correlation.

`independent_joint_probability` and `independent_combination_hold` require the keyword `assume_independent=True`. Their default rejects the calculation. An explicit assumption is recorded by the calling application; it is not evidence that events really are independent. Pairwise bounds apply to one intersection and do not establish global coherence across several markets.

## Price and margin convention

`decimal_odds(p, hold)` computes `(1-hold)/p`. Here, `hold` means expected revenue per unit stake under the supplied probability. It is distinct from the overround of an entire set of quoted outcomes. `expected_return(p, odds)` computes `p*odds-1`, including the original stake in the gross winning payout.

Zero-probability quotes, non-finite results and decimal payouts below one are rejected. With equally margined independent legs, the combined expected hold is `1-(1-hold)**legs`. Changing the correlation changes the expected hold at the same posted combination price.

## Recomputed paper example

`whitepaper_example()` recomputes Appendix A from its stated inputs. No live match or fitted model is represented.

| Quantity | Recomputed value |
| --- | ---: |
| Poisson mean for second-half corners | 5.2 |
| Probability of at least five corners | 0.5938719984274374 |
| Supplied goals-event probability | 0.55 |
| Supplied Bernoulli correlation | 0.15 |
| Joint probability assuming independence | 0.3266295991350906 |
| Correlated joint probability | 0.3632781453791876 |
| Lower pairwise intersection bound | 0.1438719984274375 |
| Upper pairwise intersection bound | 0.55 |
| Decimal odds with 8% expected hold and the correlated model | 2.532494761113993 |
| Decimal odds with 8% expected hold and independence | 2.816646141182991 |
| Expected net return at the independence quote, under the correlated model | 0.0232259863584021 |
| Uniform binary LMSR maximum loss with `b=500` | 346.5735902799726 |

These values agree with the paper's rounded illustration. The calculated 2.3226% return depends entirely on its assumed model. It is not a measured trading edge. The combination counts in section 5 are also reproduced: 1,088,651,720 for 50 binary markets with at most six legs, and 5,356,338,430,880 for 200 markets.

`poisson_tail(mean, threshold)` returns `P[X >= threshold]`. The threshold is inclusive. The implementation computes the smaller tail directly, using a log-probability starting point and recurrence, to reduce cancellation in small upper tails. It supports a mean no greater than 1,000 and an integer threshold no greater than 10,000. Extremely small probabilities can underflow to zero in floating-point arithmetic. Optional tests compare results with SciPy's independently implemented Poisson survival function.

## LMSR calculations

`lmsr_cost`, `lmsr_prices` and `lmsr_trade_cost` implement the cost function, softmax prices and cost difference using shifted exponentials. Subtracting the largest quantity before exponentiation avoids ordinary exponential overflow. Extreme price differences can still underflow to a zero floating-point price.

`lmsr_max_loss(b, outcomes)` returns `b*log(outcomes)`. That statement assumes a fixed positive liquidity parameter, mutually exclusive and exhaustive unit-payoff outcomes, zero initial outstanding quantities and the corresponding uniform starting prices. It does not bound losses from credit risk, fees, implementation errors, a changing liquidity parameter or unrelated operator positions. The code performs calculations only; it has no inventory, payment or trading integration.

## Finite-outcome coherence

`coherence_check(payoffs, lower, upper, outcomes_exhaustive=True)` constructs the feasibility problem:

```text
lower <= payoffs @ probabilities <= upper
sum(probabilities) == 1
0 <= probabilities <= 1
```

Each row is a binary claim's payoff and each column is one possible joint outcome. The caller must supply every possible joint outcome and explicitly assert that the list is exhaustive. Without that assertion, the result is `UNKNOWN`. The software cannot determine whether a real-world outcome was omitted from the caller's model.

The check uses SciPy's `linprog` with the HiGHS solver. It caps the problem at 64 claims and 256 outcomes, sets a two-second solver time limit and a 10,000-iteration limit, and checks the returned witness against a `1e-9` residual tolerance. Results are:

| Status | Meaning |
| --- | --- |
| `COHERENT` | The solver produced a finite probability witness satisfying the supplied constraints within the stated numerical tolerance |
| `INCOHERENT` | The solver reported the supplied finite problem infeasible |
| `UNKNOWN` | Exhaustiveness was unasserted, the optional solver was unavailable, computation was inconclusive, or the returned witness failed validation |

This is floating-point feasibility, not a formally verified proof or a universal market certificate. A sampled subset of outcomes cannot be substituted for an exhaustive outcome space. Prices should be expressed as the appropriate normalized unit-payoff bounds; raw decimal odds are not direct probability constraints. Transaction costs, position limits, execution rules and the legal availability of contracts require their own analysis.

The regression suite contains a useful counterexample: three events each have probability one half, and each pair has intersection probability zero. Every pair individually satisfies its intersection bounds. Their joint requirements are impossible because three disjoint events would have total probability 1.5. The full finite-outcome solver rejects the system.

## Bounded simulation

`simulate_joint` samples a caller-supplied finite joint distribution using a local seeded generator. The caller identifies which outcome indices count as success. The function also returns the finite model's exact success probability, making this deliberately small demonstration independently inspectable.

For `n` independent Bernoulli observations and confidence `1-alpha`, the two-sided Hoeffding error bound used is `sqrt(log(2/alpha)/(2*n))`. The result is `WITHIN_ERROR_BUDGET` only when that bound is no larger than the requested error budget; otherwise it is `REJECTED_ERROR_BUDGET`. At 95% confidence, 20,000 samples give a bound of approximately 0.009603. One hundred samples do not support an error budget of 0.01.

The sampling statement is conditional on independent draws from the supplied model. It excludes model misspecification, data selection, estimation error in the inputs, distribution shift, pseudorandom-generator limitations and real-world calibration. Reporting the exact finite-model probability alongside the estimate does not validate that model against sport.

Distributions must sum to one within `1e-12`. The code normalizes any residual floating-point difference and reports the input sum and whether that adjustment occurred. It never repairs a materially invalid distribution. Work is capped at 256 outcomes and one million samples; outcome indices must be distinct and valid. Reusing the same seed, model and supported Python runtime reproduces the simulation.

## Other calculations and input handling

`posterior_alert_probability` calculates positive predictive value from supplied sensitivity, specificity and base rate. It rejects a conditional probability with a zero denominator. The illustrative base-rate results are approximately 8.68% and 48.74% for sensitivity 0.95, base rate 0.001 and specificity 0.99 or 0.999 respectively. These are mathematical examples, not measured integrity-detector performance.

`event_window_probability` assumes a homogeneous Poisson process and explicitly uses rates per second and windows in seconds. `deterrence_limit` reproduces the paper's risk-neutral model `(p*sanction + direct_cost)/(decimal_odds-1)`. The latter is an illustration, not a recommended exposure limit or evidence that misconduct will be deterred.

All public functions reject booleans where numeric inputs are required, non-finite values and unsupported dimensions. `PricingError` is a `ValueError` carrying a machine-readable `code`. Integer-only fields reject floating-point substitutes. Liquidity, inventory and payout magnitudes have explicit caps rather than accepting unbounded computation or output.

## Sources and verification

The foundational whitepaper supplies the project-specific assumptions and examples. The implementation independently recomputes the numerical examples. The following primary documentation and research identify the underlying numerical methods:

- SciPy, [linear programming interface](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linprog.html): inequality and equality constraints, solver status and numerical limits.
- SciPy, [Poisson distribution](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.poisson.html): probability mass function and survival-function convention.
- Robin Hanson, [Logarithmic Market Scoring Rules for Modular Combinatorial Information Aggregation](https://hanson.gmu.edu/mktscore.pdf), *Journal of Prediction Markets* 1(1) (2007), 3–15; [publisher record](https://www.ubplj.org/index.php/jpm/article/view/417).
- Wassily Hoeffding, [Probability Inequalities for Sums of Bounded Random Variables](https://www.tandfonline.com/doi/abs/10.1080/01621459.1963.10500830), *Journal of the American Statistical Association* 58(301) (1963), 13–30. The publisher record was discoverable; direct article access was restricted during this build. The code's specific two-sided Bernoulli bound is stated explicitly above.

Run the focused suite with `python -m unittest discover -s tests -p test_pricing.py -v` after installing the package, or with `PYTHONPATH=src` from a checkout. SciPy-dependent tests skip if the optional solver is absent; the missing-solver behaviour itself is always tested. Successful internal tests establish implementation checks on the supplied cases. Independent calibration, live-market performance and deployment fitness remain unestablished.
