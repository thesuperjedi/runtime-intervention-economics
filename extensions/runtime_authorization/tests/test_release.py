"""New publication arithmetic/schema tests, not experiments or policy validation."""
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import ast
import tempfile
import unittest
import reproduce as r
import verify_package as v

class ReconstructionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ex2 = r.load("studies/ex2/evidence.json")
        cls.rec = r.load("studies/ex2_r/evidence.json")
        cls.ref = r.load("analysis/reference.json")
        cls.result = r.reconstruct(cls.ex2, cls.rec, cls.ref)

    def invalid(self, mutate, recovery=False):
        a, b = deepcopy(self.ex2), deepcopy(self.rec)
        mutate(b if recovery else a)
        with self.assertRaises(ValueError):
            r.validate(a, b)

    def test_complete_populations(self):
        self.assertTrue(r.validate(self.ex2, self.rec))
        self.assertEqual(len(self.ex2["episodes"]), 216)
        self.assertEqual(len(self.rec["episodes"]), 12)

    def test_no_cross_study_pooling(self):
        self.assertEqual(len(self.ex2["calls"]), 368)
        self.assertEqual(len(self.rec["calls"]), 21)
        self.assertFalse({e["key"] for e in self.ex2["episodes"]} & {e["key"] for e in self.rec["episodes"]})

    def test_exact_reference_tables(self):
        self.assertTrue(r.verify_reference(self.result, self.ex2, self.ref))

    def test_procurement_goal_denominators(self):
        for m, expected in (("gemini", [25,15,15]), ("claude", [8,6,10])):
            for arm, count in zip(r.ARMS, expected):
                o = self.result["EX2"][m][arm]["PRIMARY_EXCLUDING_S11"]["outcomes"]
                self.assertEqual((o["scheduled"], o["goal_true"]), (33, count))

    def test_permitted_goals(self):
        for m, expected in (("gemini", [15,15,15]), ("claude", [5,6,10])):
            self.assertEqual([self.result["EX2"][m][a]["PRIMARY_EXCLUDING_S11"]["outcomes"]["permitted_true"] for a in r.ARMS], expected)

    def test_s11_preserved(self):
        rows = [e for e in self.ex2["episodes"] if e["scenario"] == "S11"]
        self.assertEqual(len(rows), 18)
        self.assertEqual(sum(e["goal"] for e in rows if e["model"] == "gemini"), 9)
        self.assertEqual(sum(e["goal"] for e in rows if e["model"] == "claude"), 0)

    def test_b0_qualified_is_null(self):
        rows = [e for e in self.ex2["episodes"] if e["arm"] == "B0"]
        self.assertEqual(len(rows), 72)
        self.assertTrue(all(e["qualified"] is None for e in rows))

    def test_unpermitted_effect_provenance(self):
        self.assertEqual(sum(e["unpermitted_effects"] for e in self.ex2["episodes"] if e["arm"] == "B0"), 13)
        self.assertEqual(sum(e["unpermitted_effects"] for e in self.ex2["episodes"] if e["arm"] != "B0"), 0)

    def test_zero_eligible_is_not_zero_percent(self):
        self.assertTrue(all(x["effectiveness"] == "NOT_APPLICABLE" for x in self.result["EX2_recovery"].values()))

    def test_recovery_outcomes(self):
        self.assertEqual(sum(e["seed_verified"] for e in self.rec["episodes"]), 12)
        self.assertEqual(sum(e["compliant_recovery"] for e in self.rec["episodes"]), 0)
        self.assertEqual(sum(e["unpermitted_effects"] for e in self.rec["episodes"]), 0)

    def test_recovery_workflow_categories(self):
        gemini = [e for e in self.rec["episodes"] if e["model"] == "gemini"]
        self.assertTrue(all([a.get("action") for a in e["sequence_categories"]] == ["SUBMIT_PR","SUBMIT_PR"] for e in gemini))
        self.assertTrue(all(e["stop"] == "DENY" for e in gemini))
        self.assertTrue(all(e["duplicate_submission"] for e in gemini))
        self.assertEqual(sum(e["published_effects"] for e in self.rec["episodes"]), 9)

    def test_recovery_limit(self):
        self.assertTrue(all(e["model_generations"] <= 2 for e in self.rec["episodes"]))
        self.invalid(lambda b: b["episodes"][0].update(model_generations=3), True)

    def test_missing_usage_not_zero(self):
        gemini = [c for c in self.ex2["calls"] if c["model"] == "gemini"]
        self.assertTrue(all(c["thinking"] is None for c in gemini))
        self.assertIsNone(r.resource(gemini, self.ref["rates_usd_per_million"])["thinking_reported_sum"])

    def test_explicit_thinking_zero(self):
        claude = [c for c in self.ex2["calls"] if c["model"] == "claude"]
        self.assertTrue(all(c["thinking"] == 0 for c in claude))
        self.assertEqual(r.resource(claude, self.ref["rates_usd_per_million"])["thinking_missing"], 0)

    def test_cache_missing_no_credit(self):
        c = deepcopy(self.ex2["calls"][0]); c["cached"] = None
        value = r.money(c, self.ref["rates_usd_per_million"])
        c["cached"] = 0
        self.assertEqual(value, r.money(c, self.ref["rates_usd_per_million"]))

    def test_cache_subset_credit(self):
        c = deepcopy(self.ex2["calls"][0]); c["cached"] = 0
        gross = r.money(c, self.ref["rates_usd_per_million"])
        c["cached"] = 100
        self.assertEqual(gross-r.money(c, self.ref["rates_usd_per_million"]), Decimal("0.000009"))

    def test_historical_liabilities_preserved(self):
        p = self.ref["programme"]
        self.assertEqual(Decimal(p["historical_unresolved_usd"]), Decimal("0.0027984"))
        self.assertEqual(Decimal(p["cumulative_retained_usd"]), Decimal(p["historical_retained_usd"]) + Decimal(p["new_study_retained_usd"]))
        self.assertIsNone(p["actual_invoiced_usd"])

    def test_missing_identity_rejected(self):
        self.invalid(lambda b: b["episodes"].pop())

    def test_reordered_identity_rejected(self):
        self.invalid(lambda b: b["episodes"].reverse())

    def test_unknown_fields_rejected(self):
        self.invalid(lambda b: b["episodes"][0].update(unreviewed="excluded"))

    def test_private_metadata_rejected(self):
        self.invalid(lambda b: b["calls"][0].update(endpoint="excluded"))

    def test_duplicate_call_rejected(self):
        self.invalid(lambda b: b["calls"].append(b["calls"][0]))

    def test_missing_required_usage_rejected(self):
        self.invalid(lambda b: b["calls"][0].update(input=None))

    def test_negative_usage_rejected(self):
        self.invalid(lambda b: b["calls"][0].update(generated=-1))

    def test_inconsistent_cache_rejected(self):
        self.invalid(lambda b: b["calls"][0].update(cached=999999))

    def test_unsettled_call_rejected(self):
        self.invalid(lambda b: b["calls"][0].update(generation_status="HOLD"))

    def test_invalid_seed_rejected(self):
        self.invalid(lambda b: b["episodes"][0].update(seed_verified=False), True)

    def test_wrong_provenance_rejected(self):
        self.invalid(lambda b: b["episodes"][0].update(effect_provenance="AUTHENTICATED_NATIVE"))

    def test_reference_tamper_rejected(self):
        ref = deepcopy(self.ref); ref["ex2_resources"][0]["input_tokens"] += 1
        with self.assertRaises(ValueError):
            r.verify_reference(self.result, self.ex2, ref)

    def test_matched_denominators(self):
        self.assertTrue(all(sum(row.values()) == 33 for rows in self.result["matched"].values() for row in rows.values()))

class PublicPackageTests(unittest.TestCase):
    def test_exact_allowlist_and_hashes(self):
        self.assertEqual(v.verify()["files"], 40)

    def test_no_sdk_imports(self):
        self.assertEqual(v.sensitive_review()["findings"], [])

    def test_recursive_sensitive_field(self):
        result = v.structured_findings({"a":[{"api_key":None}]}, "example")
        self.assertEqual(len(result), 1)
        self.assertNotIn("value", result[0])

    def test_recognized_provider_pattern(self):
        dummy = "AI" + "za" + "x"*35
        result = v.scan_text(dummy, "example")
        self.assertTrue(any(x["category"] == "google_credential" for x in result))
        self.assertTrue(all(dummy not in str(x) for x in result))

    def test_extra_file_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/"unexpected.txt").write_text("not allowed")
            with self.assertRaises(ValueError):
                v.verify(Path(d))

    def test_mechanism_scope_is_explicit(self):
        text = (r.ROOT/"README.md").read_text()
        self.assertIn("deterministic demonstrations", text)
        self.assertTrue((r.ROOT/"mechanism/pap/evaluator.py").exists())
        self.assertFalse((r.ROOT/"mechanism/provider_binding.py").exists())
