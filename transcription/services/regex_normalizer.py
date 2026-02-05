import re
from dataclasses import dataclass
from typing import Iterable, List, Tuple, Dict

from .kolokwa_normalizer import KOLOKWA_PATTERNS


@dataclass(frozen=True)
class NormalizationRule:
    """
    A normalization rule with one or more regex patterns.
    """
    patterns: List[str]
    replacement: str
    priority: int = 0


class NormalizerEngine:
    """
    Apply regex-based normalization rules in priority order.
    Tracks per-rule confidence (1 if matched, 0 if not).
    """
    def __init__(self, rules: Iterable[NormalizationRule]):
        self.rules = sorted(list(rules), key=lambda r: r.priority, reverse=True)
        self._compiled: List[Tuple[NormalizationRule, List[re.Pattern]]] = [
            (rule, [re.compile(pat, re.IGNORECASE) for pat in rule.patterns])
            for rule in self.rules
        ]

    def normalize(self, text: str) -> Tuple[str, float, List[Dict[str, object]]]:
        """
        Normalize text and return:
        - normalized_text
        - overall_confidence (0.0 - 1.0)
        - report: list of fired rules with per-rule confidence
        """
        out = text
        report: List[Dict[str, object]] = []

        for rule, patterns in self._compiled:
            matched = False
            for pattern in patterns:
                if pattern.search(out):
                    matched = True
                    out = pattern.sub(rule.replacement, out)

            report.append(
                {
                    "replacement": rule.replacement,
                    "patterns": rule.patterns,
                    "priority": rule.priority,
                    "confidence": 1 if matched else 0,
                }
            )

        if out:
            out = out[0].upper() + out[1:]

        if report:
            overall_confidence = sum(r["confidence"] for r in report) / len(report)
        else:
            overall_confidence = 0.0

        return out, overall_confidence, report


def build_rules_from_kolokwa_patterns(
    patterns: List[Tuple[str, str]],
) -> List[NormalizationRule]:
    """
    Convert KOLOKWA_PATTERNS into NormalizationRule objects.
    Earlier patterns get higher priority.
    """
    total = len(patterns)
    rules: List[NormalizationRule] = []
    for idx, (pattern, replacement) in enumerate(patterns):
        priority = total - idx
        rules.append(
            NormalizationRule(
                patterns=[pattern],
                replacement=replacement,
                priority=priority,
            )
        )
    return rules


DEFAULT_ENGINE = NormalizerEngine(build_rules_from_kolokwa_patterns(KOLOKWA_PATTERNS))


def normalize_text(text: str) -> str:
    """
    Normalize text using the default engine and return normalized text only.
    """
    normalized, _confidence, _report = DEFAULT_ENGINE.normalize(text)
    return normalized


# Example usage
if __name__ == "__main__":
    engine = NormalizerEngine(build_rules_from_kolokwa_patterns(KOLOKWA_PATTERNS))
    sample = "I na know wetin da one mean."
    normalized_text, overall_conf, fired_rules = engine.normalize(sample)
    print("Normalized:", normalized_text)
    print("Overall confidence:", overall_conf)
    print("Fired rules:", [r for r in fired_rules if r["confidence"] == 1])
