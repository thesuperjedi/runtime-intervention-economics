"""Synthetic E2F scoring tests: no API and no writes to frozen evidence."""
import json
import unittest
from src import e2_analyse_full as a

USAGE = {"total_input_tokens":100,"total_output_tokens":10,
         "total_thought_tokens":20,"total_tokens":130,
         "total_cached_tokens":0,"total_tool_use_tokens":0}


def validator(verdict="PASS", **overrides):
    record = {"success":True,"response_text":json.dumps({"verdict":verdict}),
              "parsed_response":{"verdict":verdict},"response_valid":True,"usage":dict(USAGE)}
    record.update(overrides)
    return record


class E2FullAnalysisTests(unittest.TestCase):
    def row(self, correct, verdict):
        return a.score_observation(correct, True, validator(verdict), .01, .1, "cheap")

    def test_four_confusion_cells_and_cascade(self):
        for correct, verdict, classification, final, escalate in (
            (True,"PASS","true_accept",True,False),
            (False,"PASS","false_accept",False,False),
            (False,"FAIL","true_reject",True,True),
            (True,"FAIL","false_reject",True,True),
        ):
            with self.subTest(classification=classification):
                row = self.row(correct,verdict)
                self.assertEqual(row["classification"],classification)
                self.assertEqual(row["final_correct"],final)
                self.assertEqual(row["escalation"],escalate)
                self.assertEqual(row["escalation_cost_estimate_usd"],.1 if escalate else 0)

    def test_failed_strong_remains_incorrect_after_escalation(self):
        row = a.score_observation(False,False,validator("FAIL"),.01,.1,"strong")
        self.assertFalse(row["final_correct"])

    def test_failed_validator_is_not_a_reject(self):
        row = a.score_observation(False,True,validator(success=False),.01,.1,"cheap")
        self.assertEqual(row["status"],"failed")
        self.assertIsNone(row["classification"])
        self.assertIsNone(row["final_correct"])
        self.assertIsNone(row["escalation_cost_estimate_usd"])

    def test_missing_is_unknown_not_zero_cost(self):
        row = a.score_observation(False,True,None,.01,.1,"cheap")
        self.assertEqual(row["status"],"missing")
        self.assertIsNone(row["validator_cost_estimate_usd"])
        self.assertIsNone(row["total_cost_estimate_usd"])

    def test_malformed_response_cases(self):
        for text in ("broken","{}",'{"verdict":"MAYBE"}','{"verdict":[]}',
                     '["PASS"]','{"verdict":"PASS","extra":1}'):
            with self.subTest(text=text):
                status, verdict = a.validator_status({"success":True,"response_text":text})
                self.assertEqual(status,"malformed")
                self.assertIsNone(verdict)

    def test_persisted_validity_and_parsed_mismatch_detected(self):
        for record in (validator(response_valid=False),validator(parsed_response={"verdict":"FAIL"})):
            with self.assertRaises(ValueError):
                a.validator_status(record)

    def test_cost_thought_inclusion_and_no_extra_telemetry_addition(self):
        record = validator()
        record["usage"]["raw_prompt_token"]=999999
        record["usage"]["model_invocation_token_counts"]=[{"tokens":999999}]
        self.assertAlmostEqual(a.estimated_record_cost(record,"cheap"),.000105)
        self.assertAlmostEqual(a.estimated_record_cost(record,"strong"),.0001875)
        row = a.score_observation(False,True,record,.01,.1,"cheap")
        self.assertAlmostEqual(row["total_cost_estimate_usd"],.010105)

    def test_unknown_or_unsupported_usage_not_imputed(self):
        for usage in (None,{},dict(USAGE,total_tokens=999),
                      dict(USAGE,total_cached_tokens=5),dict(USAGE,total_tool_use_tokens=5)):
            with self.subTest(usage=usage):
                self.assertIsNone(a.estimated_record_cost(validator(usage=usage),"cheap"))

    def test_far_frr_and_coverage_denominators(self):
        rows = [self.row(True,"PASS"),self.row(True,"FAIL"),
                self.row(False,"PASS"),self.row(False,"FAIL"),
                a.score_observation(False,True,None,.01,.1,"cheap")]
        summary = a.summarize(rows)
        self.assertEqual(summary["FAR_valid_verdicts"],{"numerator":1,"denominator":2,"value":.5})
        self.assertEqual(summary["FRR_valid_verdicts"],{"numerator":1,"denominator":2,"value":.5})
        self.assertEqual(summary["incorrect_cheap_valid_coverage"]["denominator"],3)
        self.assertEqual(summary["final_accuracy_resolved_only"]["value"],.75)
        self.assertEqual(summary["unresolved_final_results"],1)
        self.assertIsNone(summary["costs"]["total"]["complete_total_usd"])
        self.assertEqual(summary["costs"]["total"]["unknown_count"],1)

    def test_empty_denominators_are_null(self):
        summary = a.summarize([])
        self.assertIsNone(summary["FAR_valid_verdicts"]["value"])
        self.assertIsNone(summary["FRR_valid_verdicts"]["value"])
        self.assertIsNone(summary["cost_per_correct_complete_subset"]["estimated_usd"])

    def test_cost_per_correct_counts_incorrect_result_costs(self):
        rows = [self.row(True,"PASS"),self.row(False,"PASS")]
        summary = a.summarize(rows)
        self.assertEqual(summary["cost_per_correct_complete_subset"]["correct_results"],1)
        self.assertAlmostEqual(summary["cost_per_correct_complete_subset"]["estimated_usd"],.02021)

    def test_unresolved_validator_cost_breakdown(self):
        for status, record in (
            ("failed", validator(success=False)),
            ("malformed", validator(response_text="broken", parsed_response=None,
                                    response_valid=False)),
            ("missing", None),
        ):
            with self.subTest(status=status):
                row = a.score_observation(False, True, record, .01, .1, "cheap")
                unknown_row = a.score_observation(False, True,
                    None if record is None else dict(record, usage=None), .01, .1, "cheap")
                summary = a.summarize([row, unknown_row])
                breakdown = summary["unresolved_validator_costs"][status]
                self.assertEqual(breakdown["observation_count"], 2)
                known_count = 0 if status == "missing" else 1
                self.assertEqual(breakdown["known_validator_cost_count"], known_count)
                self.assertEqual(breakdown["unknown_validator_cost_count"], 2-known_count)
                self.assertAlmostEqual(breakdown["known_validator_cost_sum_estimate_usd"],
                                       0 if status == "missing" else .000105)
                if status != "missing":
                    self.assertAlmostEqual(row["validator_cost_estimate_usd"], .000105)
                else:
                    self.assertIsNone(row["validator_cost_estimate_usd"])
                for unresolved in (row, unknown_row):
                    self.assertIsNone(unresolved["escalation_cost_estimate_usd"])
                    self.assertIsNone(unresolved["total_cost_estimate_usd"])
                    self.assertIsNone(unresolved["final_correct"])

    def test_complete_case_cost_per_correct_excludes_unresolved_and_unknown_cost(self):
        valid_rows = [self.row(True, "PASS"), self.row(False, "FAIL")]
        unresolved = [
            a.score_observation(True, True, validator(success=False), .01, .1, "cheap"),
            a.score_observation(True, True, validator(response_text="broken",
                parsed_response=None, response_valid=False), .01, .1, "cheap"),
            a.score_observation(True, True, None, .01, .1, "cheap"),
            a.score_observation(True, True, validator(usage=None), .01, .1, "cheap"),
        ]
        baseline = a.summarize(valid_rows)
        summary = a.summarize(valid_rows + unresolved)
        metric = summary["cost_per_correct_complete_subset"]
        self.assertEqual(metric["estimated_usd"],
                         baseline["cost_per_correct_complete_subset"]["estimated_usd"])
        self.assertEqual(metric["rows_with_resolved_route_and_cost"], 2)
        self.assertEqual(metric["correct_results"], 2)
        self.assertEqual(metric["excluded_observation_count"], 4)
        self.assertIn("Complete-case, resolved-route", metric["description"])
        self.assertIn("not unconditional operational", metric["description"])
        self.assertEqual(summary["confusion"], {
            "true_accept": 2, "false_accept": 0, "true_reject": 1, "false_reject": 0})
        self.assertEqual(summary["unresolved_final_results"], 3)
        self.assertAlmostEqual(summary["costs"]["validator"]["known_subtotal_usd"], .00042)

    def test_frozen_oracle_full_manifest_read_only_integration(self):
        result = a.analyse(a.ROOT/"config/e2_full_manifest_v1.json")
        rows = result["observations"]
        self.assertEqual(len(rows),1620)
        self.assertEqual(len({r["run_id"] for r in rows}),1620)
        self.assertEqual({r["status"] for r in rows},{"valid"})
        for role in ("cheap_validator","strong_validator"):
            summary = result["per_model"][role]
            self.assertEqual(summary["canonical_cases"],30)
            self.assertEqual(summary["observations"],810)
            self.assertEqual(summary["unresolved_final_results"],0)
        first = result["per_model_repetition"]["cheap_validator/R001"]
        self.assertEqual(first["correct_cheap_valid_coverage"]["denominator"],236)
        self.assertEqual(first["incorrect_cheap_valid_coverage"]["denominator"],34)
        self.assertIsNotNone(first["costs"]["total"]["complete_total_usd"])


if __name__=="__main__":
    unittest.main()
