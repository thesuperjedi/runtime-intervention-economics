"""E3 Stage 1: correctness-only, hypothetical human reviewer.

The oracle is used ONLY by the evaluator/simulator to condition outcomes;
no routing policy or real-human review interface is implemented here.
No actual replacement control sets are produced. No external calls.
"""
from dataclasses import dataclass
from itertools import product
import math
import random


@dataclass(frozen=True)
class ReviewerProfile:
    D: float  # probability of REPLACE when input set is wrong
    C: float  # probability of exact correction given REPLACE and wrong input
    F: float  # probability of wrong REPLACE when input set is correct

    def __post_init__(self):
        for name in ('D', 'C', 'F'):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1:
                raise ValueError(f'{name} must be finite and in [0,1]')


def primary_grid():
    return [ReviewerProfile(*values) for values in product((.25, .5, .75, 1.), (.5, .75, 1.), (0., .05, .15))]


def exact_set_match(proposed_controls, expected_controls):
    """Strict set match: lists/tuples of unique strings, including empty sets."""
    def checked(values):
        if not isinstance(values, (list, tuple)) or any(not isinstance(x, str) for x in values):
            raise ValueError('controls must be a list/tuple of strings')
        if len(values) != len(set(values)):
            raise ValueError('duplicate controls')
        return frozenset(values)
    return checked(proposed_controls) == checked(expected_controls)


def review_distribution(ai_correct, profile):
    """Distribution on (action, final_exact_correct); no fabricated outputs."""
    if not isinstance(ai_correct, bool):
        raise ValueError('ai_correct must be boolean')
    if ai_correct:
        return {('RETAIN', True): 1 - profile.F, ('REPLACE', False): profile.F}
    return {('RETAIN', False): 1 - profile.D,
            ('REPLACE', True): profile.D * profile.C,
            ('REPLACE', False): profile.D * (1 - profile.C)}


def expected_accuracy(correctness, profile):
    """Exact expectation across the specific reviewed observations."""
    flags = list(correctness)
    if not flags or any(not isinstance(x, bool) for x in flags):
        raise ValueError('nonempty boolean correctness sequence required')
    p = sum(flags) / len(flags)
    return p * (1 - profile.F) + (1 - p) * profile.D * profile.C


def expected_routed_accuracy(items, profile):
    """Items: (initially_correct:bool, routed_to_human:bool)."""
    rows = list(items)
    if not rows or any(not isinstance(a, bool) or not isinstance(b, bool) for a, b in rows):
        raise ValueError('nonempty (boolean,boolean) pairs required')
    return sum(
        (1 - profile.F if correct else profile.D * profile.C) if routed else float(correct)
        for correct, routed in rows
    ) / len(rows)


def sample_review(ai_correct, profile, rng):
    distribution = review_distribution(ai_correct, profile)
    draw = rng.random()
    cumulative = 0.0
    for outcome, weight in distribution.items():
        cumulative += weight
        if draw < cumulative:
            return outcome
    return next(reversed(distribution))


def sample_routed_accuracy(items, profile, seed):
    rng = random.Random(seed)
    rows = list(items)
    if not rows:
        raise ValueError('empty observations')
    return sum(sample_review(correct, profile, rng)[1] if routed else correct
               for correct, routed in rows) / len(rows)
