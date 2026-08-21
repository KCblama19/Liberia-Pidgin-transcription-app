import re

from dataclasses import dataclass
from typing import Iterable, List, Tuple, Dict

from .kolokwa_normalizer import (
    KOLOKWA_PATTERNS,
)


@dataclass(frozen=True)
class NormalizationRule:
    """
    A normalization rule containing one or more
    regular-expression patterns.
    """
    patterns: List[str]
    replacement: str
    priority: int = 0


class NormalizerEngine:
    """
    Apply normalization rules in priority order.

    The engine returns:

    - normalized text
    - rule match ratio
    - a report of rules that actually matched
    """

    def __init__(
        self,
        rules: Iterable[NormalizationRule],
    ):
        self.rules = sorted(
            list(rules),
            key=lambda rule: rule.priority,
            reverse=True,
        )

        self._compiled: List[
            Tuple[
                NormalizationRule,
                List[re.Pattern],
            ]
        ] = [
            (
                rule,
                [
                    re.compile(
                        pattern,
                        re.IGNORECASE,
                    )
                    for pattern in rule.patterns
                ],
            )
            for rule in self.rules
        ]

    def normalize(
        self,
        text: str,
    ) -> Tuple[
        str,
        float,
        List[Dict[str, object]],
    ]:
        """
        Normalize text.

        Returns:

        normalized_text
        rule_match_ratio
        matched_rules
        """
        if not text:
            return text, 0.0, []

        output = text

        matched_rules: List[
            Dict[str, object]
        ] = []

        total_rules = len(
            self._compiled
        )

        matched_rule_count = 0

        for rule, patterns in self._compiled:
            matched = False

            for pattern in patterns:
                if pattern.search(output):
                    matched = True

                    output = pattern.sub(
                        rule.replacement,
                        output,
                    )

            if matched:
                matched_rule_count += 1

                matched_rules.append(
                    {
                        "replacement": (
                            rule.replacement
                        ),
                        "patterns": rule.patterns,
                        "priority": (
                            rule.priority
                        ),
                    }
                )

        output = re.sub(
            r"\s+",
            " ",
            output,
        ).strip()

        if output:
            output = (
                output[0].upper()
                + output[1:]
            )

        rule_match_ratio = (
            matched_rule_count / total_rules
            if total_rules
            else 0.0
        )

        return (
            output,
            rule_match_ratio,
            matched_rules,
        )


def build_rules_from_kolokwa_patterns(
    patterns: List[
        Tuple[str, str]
    ],
) -> List[NormalizationRule]:
    """
    Convert Kolokwa pattern tuples into prioritized
    normalization rules.

    Earlier rules have higher priority.
    """
    total = len(patterns)

    rules: List[
        NormalizationRule
    ] = []

    for index, (
        pattern,
        replacement,
    ) in enumerate(patterns):

        priority = (
            total - index
        )

        rules.append(
            NormalizationRule(
                patterns=[
                    pattern
                ],
                replacement=replacement,
                priority=priority,
            )
        )

    return rules


DEFAULT_ENGINE = NormalizerEngine(
    build_rules_from_kolokwa_patterns(
        KOLOKWA_PATTERNS
    )
)


def normalize_text(
    text: str,
) -> str:
    """
    Normalize text and return only the normalized result.
    """
    normalized, _, _ = (
        DEFAULT_ENGINE.normalize(
            text
        )
    )

    return normalized