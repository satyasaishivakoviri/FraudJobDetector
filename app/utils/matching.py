from typing import Any, Dict, List, Optional
from rapidfuzz import fuzz, utils

MATCH_THRESHOLD = 80.0


def match_company_name(
    claimed_name: str,
    registry_results: List[Dict[str, Any]],
    threshold: float = MATCH_THRESHOLD,
) -> Dict[str, Any]:
    """
    Compare a claimed company name against the 'name' field of each registry result
    using rapidfuzz's token_sort_ratio.

    Returns a dict with:
        - best_match: dict or None (the highest scoring registry record)
        - score: float (similarity score from 0.0 to 100.0)
        - no_match: bool (True if the best score is below threshold, False otherwise)
        - claimed_name: str
    """
    if not isinstance(claimed_name, str) or not claimed_name.strip() or not registry_results:
        return {
            "claimed_name": claimed_name if isinstance(claimed_name, str) else "",
            "best_match": None,
            "score": 0.0,
            "no_match": True,
        }

    clean_claimed = claimed_name.strip()
    best_record: Optional[Dict[str, Any]] = None
    best_score: float = -1.0

    for result in registry_results:
        if not isinstance(result, dict):
            continue

        # Look for 'name' field as specified; fallback to common company name keys if absent
        candidate_name = result.get("name")
        if candidate_name is None:
            candidate_name = result.get("company_name") or result.get("legal_name") or result.get("enterprise_name")

        if not candidate_name or not isinstance(candidate_name, str):
            continue

        # token_sort_ratio with default_process to handle case-insensitivity and punctuation
        score = float(
            fuzz.token_sort_ratio(
                clean_claimed,
                candidate_name.strip(),
                processor=utils.default_process,
            )
        )

        if score > best_score:
            best_score = score
            best_record = result

    if best_record is None or best_score < 0:
        return {
            "claimed_name": clean_claimed,
            "best_match": None,
            "score": 0.0,
            "no_match": True,
        }

    rounded_score = round(best_score, 2)
    is_no_match = rounded_score < threshold

    return {
        "claimed_name": clean_claimed,
        "best_match": best_record,
        "score": rounded_score,
        "no_match": is_no_match,
    }
