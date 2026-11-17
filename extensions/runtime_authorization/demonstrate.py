"""Deterministic TEST-ONLY mechanism demonstration. Never invokes a model."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from mechanism.offline_guard import install
install(Path(__file__).resolve().parent)
import json
from verify_package import verify
from mechanism import fixtures, scoring
from mechanism.drivers import ScriptDriver
from mechanism.recovery import RecoverySession

def main():
    verify()
    result = {"classification":"NEW_DETERMINISTIC_DEMONSTRATION_NOT_EMPIRICAL_RESULTS", "test_only":True, "cases":{}}
    for condition in ("S07", "S08"):
        good = RecoverySession(condition)
        before = good.result()
        first = good.answer(good.scripted(1))
        final = good.answer(good.scripted(2))
        bad = RecoverySession(condition)
        bad.answer(bad.scripted(1))
        repeated = bad.answer(bad.scripted(1))
        result["cases"][condition] = dict(seed_verified=before["seed_verified"],
            submission_alone_completes=first["compliant_recovery"], permitted_recovery=final["compliant_recovery"],
            failed_continuation=repeated["stop"], unpermitted_effects=final["score"]["unpermitted_effects"],
            scripted_responses=final["scripted_responses"])
    baseline = ScriptDriver(fixtures.materialize("S07", "B0"))
    baseline.action(baseline.fixture["actions"][0])
    _, bscore = scoring.build_view(baseline.history, baseline.fixture["scenario"])
    result["independent_B0"] = dict(effect_count=bscore["published_effects"], unpermitted_effects=bscore["unpermitted_effects"], provenance="INDEPENDENT_SYNTHETIC_NOT_AUTHENTICATED")
    print(json.dumps(result, indent=2))
if __name__ == "__main__":
    main()
