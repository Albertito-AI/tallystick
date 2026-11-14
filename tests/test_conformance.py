"""Cross-language, known-answer and metamorphic settlement checks."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest
from copy import deepcopy

from tallystick.settlement import evaluate

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("conformance_fixtures", ROOT / "conformance/fixtures.py")
_fixtures = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fixtures)


def run_reference(cases: list[dict]) -> list[dict]:
    node = os.environ.get("CODEX_PRIMARY_RUNTIME_NODE") or shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for cross-language conformance")
    completed = subprocess.run(
        [node, str(ROOT / "conformance/reference.mjs")],
        input=json.dumps(cases), capture_output=True, text=True, check=False, timeout=30,
    )
    if completed.returncode:
        raise AssertionError(completed.stderr)
    return json.loads(completed.stdout)


class SettlementConformanceTests(unittest.TestCase):
    def compare_rows(self, rows: list[dict]) -> None:
        js = run_reference([r["input"] for r in rows])
        self.assertEqual(len(js), len(rows))
        for row, reference in zip(rows, js):
            with self.subTest(case=row["name"]):
                data = row["input"]
                actual = evaluate(data["market"], data["facts"], as_of=data["as_of"])
                self.assertEqual(actual, reference)
                for key, value in row["expected"].items():
                    self.assertEqual(actual[key], value)

    def test_golden_edge_cases(self) -> None:
        self.compare_rows(_fixtures.golden_cases())

    def test_380_match_synthetic_season_and_corrections(self) -> None:
        self.compare_rows(_fixtures.synthetic_season())

    def test_equal_timestamp_closure_requires_later_append_order(self) -> None:
        case = _fixtures.complete_case(1)
        original, closed = case["facts"][0], case["facts"][-1]
        second = _fixtures.fact("offsetting-record", value=0)
        case["facts"].insert(-1, second)
        stamp = "2026-11-04T08:00:00Z"
        earlier_ack = _fixtures.revised(closed, 1, received_at=stamp)
        case["facts"].extend([
            earlier_ack,
            _fixtures.revised(original, 0, received_at=stamp),
            _fixtures.revised(second, 1, received_at=stamp),
        ])
        self.compare_rows([{"name": "tied_receipt_closure_first",
                            "input": deepcopy(case),
                            "expected": {"status": "pending", "outcome": None, "count": None,
                                         "reasons": ["stale_closure"]}}])
        case["facts"].append(_fixtures.revised(earlier_ack, 1, received_at=stamp))
        self.compare_rows([{"name": "tied_receipt_closure_after",
                            "input": case,
                            "expected": {"status": "settled", "outcome": "under", "count": 1,
                                         "reasons": []}}])

    def test_distinct_receipt_time_and_append_order_failures(self) -> None:
        # Provisional RFC 0001 R03/R04 expectations; independent review is pending.
        stamp = "2026-11-04T08:00:00Z"
        cases = []
        for name in ("R03_later_append_earlier_timestamp",
                     "R04_earlier_append_later_timestamp"):
            case = _fixtures.complete_case(1)
            first, closed = case["facts"][0], case["facts"][-1]
            second = _fixtures.fact("offsetting-axis-record", value=0)
            case["facts"].insert(-1, second)
            corrections = [
                _fixtures.revised(first, 0, received_at=stamp),
                _fixtures.revised(second, 1, received_at=stamp),
            ]
            if name.startswith("R03"):
                # Appended after both changes but with an earlier declared time.
                ack = _fixtures.revised(
                    closed, 1, received_at="2026-11-03T21:30:00Z")
                case["facts"].extend(corrections + [ack])
            else:
                # Declared after both changes but appended before either one.
                ack = _fixtures.revised(
                    closed, 1, received_at="2026-11-04T08:01:00Z")
                case["facts"].extend([ack] + corrections)
            cases.append({"name": name, "input": case,
                          "expected": {"status": "pending", "outcome": None,
                                       "count": None, "reasons": ["stale_closure"]}})
        self.compare_rows(cases)

    def test_postclosure_initial_observations_characterisation(self) -> None:
        # RFC 0001 R08/R09: compare both first-party evaluators without
        # prescribing the contested post-closure settlement status.
        # Independent semantic review must decide the eventual contract.
        late_time = "2026-11-03T21:05:00Z"
        late_positive = _fixtures.fact(
            "late-initial-corner-r08", value=1, received_at=late_time)
        r08 = _fixtures.complete_case(0)
        r08["facts"][0]["value"] = 1  # Earlier aggregate, no occurrence yet.
        r08_before = deepcopy(r08)
        r08["facts"].append(late_positive)

        late_zero = _fixtures.fact(
            "late-initial-zero-r09", value=0, received_at=late_time)
        r09 = _fixtures.complete_case(0)
        r09_before = deepcopy(r09)
        r09["facts"].append(late_zero)

        r08_control = deepcopy(r08)
        r08_control["facts"] = [late_positive, r08_before["facts"][0]]
        r09_control = deepcopy(r09)
        r09_control["facts"] = [late_zero, r09_before["facts"][0]]

        cases = [
            ("R08_before", r08_before),
            ("R08_late_initial", r08),
            ("R08_initial_before_closure", r08_control),
            ("R09_before", r09_before),
            ("R09_late_zero_initial", r09),
            ("R09_zero_before_closure", r09_control),
        ]
        references = run_reference([data for _, data in cases])
        self.assertEqual(len(references), len(cases))
        for (name, data), reference in zip(cases, references):
            with self.subTest(case=name):
                observed = evaluate(
                    data["market"], data["facts"], as_of=data["as_of"])
                self.assertEqual(observed, reference)
        # The pre-late-occurrence R08 control has an unmatched total; this
        # is an existing aggregate gate, not an R08/R09 semantic decision.
        before = evaluate(
            r08_before["market"], r08_before["facts"],
            as_of=r08_before["as_of"])
        self.assertEqual(before["reasons"], ["closure_count_mismatch"])

    def test_unrelated_event_and_period_do_not_change_result(self) -> None:
        case = _fixtures.complete_case(5)
        baseline = evaluate(case["market"], case["facts"], as_of=case["as_of"])
        case["facts"] += _fixtures.complete_case(14, event_id="unrelated-match")["facts"]
        case["facts"].append(_fixtures.fact("other-period", period=1))
        self.assertEqual(evaluate(case["market"], case["facts"], as_of=case["as_of"]), baseline)
        self.assertEqual(run_reference([case])[0], baseline)

    def test_appending_future_revision_preserves_historical_decision(self) -> None:
        case = _fixtures.complete_case(5)
        case["as_of"] = "2026-11-03T23:00:00Z"
        baseline = evaluate(case["market"], case["facts"], as_of=case["as_of"])
        case["facts"].append(_fixtures.revised(case["facts"][0], 0,
                                                received_at="2026-11-04T08:00:00Z"))
        self.assertEqual(evaluate(case["market"], case["facts"], as_of=case["as_of"]), baseline)
        self.assertEqual(run_reference([case])[0], baseline)

    def test_reordering_independent_observations_preserves_result(self) -> None:
        case = _fixtures.complete_case(6)
        baseline = evaluate(case["market"], case["facts"], as_of=case["as_of"])
        case["facts"].reverse()
        self.assertEqual(evaluate(case["market"], case["facts"], as_of=case["as_of"]), baseline)
        self.assertEqual(run_reference([case])[0], baseline)

    def test_revision_identity_cannot_change(self) -> None:
        case = _fixtures.complete_case(5)
        revision = _fixtures.revised(case["facts"][0], 0,
                                        received_at="2026-11-04T08:00:00Z")
        revision["licence_id"] = "different-licence"
        case["facts"].append(revision)
        with self.assertRaises(ValueError):
            evaluate(case["market"], case["facts"], as_of=case["as_of"])


if __name__ == "__main__":
    unittest.main()
