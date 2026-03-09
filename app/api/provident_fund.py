"""Provident Fund (EPF) Calculation Service.

Implements Indian Employee Provident Fund interest calculation across
multiple company stints.  Key rules modelled:

1. Employee contributes a fixed monthly amount during each employment.
2. The annual interest rate is declared by EPFO (government) and applies
   to the **entire accumulated balance**, not just the current company's
   contributions.
3. Interest accrues monthly on the running balance but is compounded
   (credited) at the end of each financial year (March 31).
4. During gaps between jobs, no contributions are made but the existing
   balance continues to earn interest at the last known rate.
5. An entry with no end date means the employee is currently employed.
"""

from datetime import date
from typing import Any

from dateutil.rrule import MONTHLY, rrule

from ..constants import EPF_DEFAULT_RATE, EPF_HISTORICAL_RATES
from ..logging_config import logger
from ..utils import parse_date


def _get_epf_rate(year: int, month: int) -> float:
    """Return the official EPF interest rate for the FY containing (year, month)."""
    fy_start = year if month >= 4 else year - 1
    return EPF_HISTORICAL_RATES.get(fy_start, EPF_DEFAULT_RATE)


# ── Date helpers ──────────────────────────────────────────────────


def _month_range(start: date, end: date):
    """Yield (year, month) tuples from *start* through *end* inclusive."""
    for dt in rrule(MONTHLY, dtstart=start.replace(day=1), until=end.replace(day=1)):
        yield dt.year, dt.month


def _is_past_employer(entry: dict[str, Any]) -> bool:
    """Return True if the entry represents a past employer lump-sum balance."""
    return (
        float(entry.get("opening_balance", 0) or 0) > 0
        and float(entry.get("monthly_contribution", 0) or 0) <= 0
    )


def _safe_float(entry: dict[str, Any], key: str) -> float:
    """Extract a float from an entry dict, defaulting to 0."""
    return float(entry.get(key, 0) or 0)


# ── Parsing & classification ────────────────────────────────────


def _parse_entries(
    entries: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], date, date | None]]:
    """Parse and validate entry dates, returning (entry, start, end) tuples sorted by start."""
    parsed: list[tuple[dict[str, Any], date, date | None]] = []
    for entry in entries:
        start = parse_date(entry.get("start_date", ""))
        if not start:
            if _is_past_employer(entry):
                start = date.today()
            else:
                logger.warning(
                    "PF: skipping entry for '%s' — cannot parse start_date '%s'",
                    entry.get("company_name", "?"),
                    entry.get("start_date"),
                )
                continue
        end = parse_date(entry.get("end_date", ""))
        parsed.append((entry, start, end))

    parsed.sort(key=lambda t: t[1])
    return parsed


def _classify_entries(
    parsed: list[tuple[dict[str, Any], date, date | None]],
    today: date,
) -> tuple[set[int], dict[tuple[int, int], list[tuple[int, float, float]]]]:
    """Separate past-employer entries from active employment.

    Returns:
        past_employer_set: indices of past-employer entries.
        past_lump_schedule: {(year, month): [(idx, lump, actual), ...]}
            — lump sums to inject at the scheduled month (today).
    """
    past_employer_set: set[int] = set()
    past_lump_schedule: dict[tuple[int, int], list[tuple[int, float, float]]] = {}

    for idx, (entry, _start, _end) in enumerate(parsed):
        if _is_past_employer(entry):
            past_employer_set.add(idx)
            lump = _safe_float(entry, "opening_balance")
            actual = _safe_float(entry, "actual_contribution")
            inject_ym = (today.year, today.month)
            past_lump_schedule.setdefault(inject_ym, []).append((idx, lump, actual))

    return past_employer_set, past_lump_schedule


# ── Month-by-month timeline ─────────────────────────────────────


def _build_month_timeline(
    parsed: list[tuple[dict[str, Any], date, date | None]],
    past_employer_set: set[int],
    today: date,
) -> dict[tuple[int, int], tuple[float, float, int]]:
    """Map each (year, month) to (contribution, rate, entry_idx) for active entries."""
    month_info: dict[tuple[int, int], tuple[float, float, int]] = {}

    for idx, (entry, start, end) in enumerate(parsed):
        if idx in past_employer_set:
            continue
        contribution = _safe_float(entry, "monthly_contribution")
        rate = _safe_float(entry, "interest_rate")
        effective_end = min(end, today) if end else today
        for ym in _month_range(start, effective_end):
            month_info[ym] = (contribution, rate, idx)

    return month_info


def _init_entry_accumulators(
    parsed: list[tuple[dict[str, Any], date, date | None]],
    past_employer_set: set[int],
) -> list[dict[str, float]]:
    """Create per-entry accumulators, pre-filling past-employer data."""
    entry_data: list[dict[str, float]] = [
        {
            "opening_balance": 0.0,
            "total_contribution": 0.0,
            "interest_earned": 0.0,
            "closing_balance": 0.0,
            "months_worked": 0,
            "rate_sum": 0.0,
            "rate_months": 0,
        }
        for _ in parsed
    ]

    for idx in past_employer_set:
        entry = parsed[idx][0]
        lump = _safe_float(entry, "opening_balance")
        actual = _safe_float(entry, "actual_contribution")
        entry_data[idx]["total_contribution"] = actual if actual > 0 else lump
        entry_data[idx]["opening_balance"] = lump

    return entry_data


def _walk_timeline(
    parsed: list[tuple[dict[str, Any], date, date | None]],
    month_info: dict[tuple[int, int], tuple[float, float, int]],
    past_employer_set: set[int],
    past_lump_schedule: dict[tuple[int, int], list[tuple[int, float, float]]],
    entry_data: list[dict[str, float]],
    today: date,
) -> float:
    """Walk month-by-month from earliest active start to today, computing balances.

    Mutates *entry_data* in place.  Returns the final corpus balance.
    """
    active_starts = [start for idx, (_, start, _) in enumerate(parsed) if idx not in past_employer_set]
    earliest = min(active_starts) if active_starts else today

    first_active = next((i for i in range(len(parsed)) if i not in past_employer_set), 0)
    last_rate = _safe_float(parsed[first_active][0], "interest_rate")

    balance = 0.0
    accrued_interest_fy = 0.0
    prev_entry_idx = -1

    for ym in _month_range(earliest, today):
        # Inject past-employer lump sums at their scheduled month
        if ym in past_lump_schedule:
            for _past_idx, lump, _actual in past_lump_schedule[ym]:
                balance += lump

        info = month_info.get(ym)
        if info:
            contribution, rate, entry_idx = info
            if rate <= 0:
                rate = _get_epf_rate(ym[0], ym[1])
            last_rate = rate
        else:
            contribution = 0.0
            rate = last_rate
            entry_idx = prev_entry_idx if prev_entry_idx >= 0 else first_active

        # Record opening/closing balance on entry transitions
        if entry_idx != prev_entry_idx and 0 <= entry_idx < len(entry_data):
            if prev_entry_idx >= 0 and prev_entry_idx not in past_employer_set:
                entry_data[prev_entry_idx]["closing_balance"] = balance + accrued_interest_fy
            entry_data[entry_idx]["opening_balance"] = balance + accrued_interest_fy

        balance += contribution

        if 0 <= entry_idx < len(entry_data) and entry_idx not in past_employer_set and info:
            ed = entry_data[entry_idx]
            ed["total_contribution"] += contribution
            ed["months_worked"] += 1
            ed["rate_sum"] += rate
            ed["rate_months"] += 1

        # Monthly interest accrual — skip the current (incomplete) month
        is_current_month = ym[0] == today.year and ym[1] == today.month
        if not is_current_month:
            monthly_interest = balance * (rate / 12.0 / 100.0)
            accrued_interest_fy += monthly_interest
            if 0 <= entry_idx < len(entry_data) and entry_idx not in past_employer_set:
                entry_data[entry_idx]["interest_earned"] += monthly_interest
            # Compound at financial-year end (March)
            if ym[1] == 3:
                balance += accrued_interest_fy
                accrued_interest_fy = 0.0

        prev_entry_idx = entry_idx

    # Add uncredited interest for the current partial FY
    balance += accrued_interest_fy

    # Finalize the last active entry
    if prev_entry_idx >= 0 and prev_entry_idx < len(entry_data) and prev_entry_idx not in past_employer_set:
        entry_data[prev_entry_idx]["closing_balance"] = balance

    return balance


# ── Result enrichment ────────────────────────────────────────────


def _enrich_entry(
    entry: dict[str, Any],
    start: date,
    end: date | None,
    ed: dict[str, float],
    is_past: bool,
    today: date,
) -> dict[str, Any]:
    """Build an enriched copy of a single PF entry with calculated fields."""
    copy = dict(entry)

    original_rate = _safe_float(entry, "interest_rate")
    copy["auto_rate"] = original_rate <= 0
    if copy["auto_rate"] and ed["rate_months"] > 0:
        copy["effective_rate"] = round(ed["rate_sum"] / ed["rate_months"], 2)
    elif copy["auto_rate"] and is_past:
        copy["effective_rate"] = round(_get_epf_rate(today.year, today.month), 2)
    else:
        copy["effective_rate"] = round(original_rate, 2)

    copy["start_date_parsed"] = start.strftime("%B %d, %Y")
    copy["end_date_parsed"] = end.strftime("%B %d, %Y") if end else ""
    copy["is_current"] = end is None
    copy["is_past_employer"] = is_past
    copy["actual_contribution"] = _safe_float(entry, "actual_contribution")

    if is_past:
        input_opening = _safe_float(entry, "opening_balance")
        copy["opening_balance"] = round(input_opening, 2)
        copy["closing_balance"] = round(input_opening, 2)
        copy["months_worked"] = 0
        copy["total_contribution"] = round(ed["total_contribution"], 2)
        actual = copy["actual_contribution"]
        copy["interest_earned"] = round(input_opening - actual, 2) if actual > 0 else 0.0
    else:
        copy["months_worked"] = ed["months_worked"]
        copy["total_contribution"] = round(ed["total_contribution"], 2)
        copy["opening_balance"] = round(ed["opening_balance"], 2)
        copy["closing_balance"] = round(ed["closing_balance"], 2)
        copy["interest_earned"] = round(ed["interest_earned"], 2)

    return copy


def _build_enriched_results(
    parsed: list[tuple[dict[str, Any], date, date | None]],
    entry_data: list[dict[str, float]],
    past_employer_set: set[int],
    balance: float,
    today: date,
) -> list[dict[str, Any]]:
    """Build the final list of enriched entries with corpus totals."""
    enriched = []
    total_contributions = 0.0

    for idx, (entry, start, end) in enumerate(parsed):
        is_past = idx in past_employer_set
        copy = _enrich_entry(entry, start, end, entry_data[idx], is_past, today)
        total_contributions += entry_data[idx]["total_contribution"]
        enriched.append(copy)

    corpus = round(balance, 2)
    total_interest = round(corpus - total_contributions, 2)
    for entry in enriched:
        entry["corpus_value"] = corpus
        entry["total_corpus_contributions"] = round(total_contributions, 2)
        entry["total_corpus_interest"] = total_interest

    return enriched


# ── Core calculation ─────────────────────────────────────────────


def calculate_pf_corpus(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Enrich PF entries with calculated values.

    Each entry describes a company stint with fields:
        company_name, start_date, end_date (optional),
        monthly_contribution, interest_rate (annual %).

    Returns a new list of entries enriched with:
        - months_worked: number of contribution months
        - total_contribution: total money contributed in this stint
        - opening_balance: PF balance when this stint started
        - closing_balance: balance at the end of this stint (with interest)
        - interest_earned: interest earned during this stint (on full balance)
        - corpus_value: final accumulated PF balance across all stints
    """
    if not entries:
        return []

    parsed = _parse_entries(entries)
    if not parsed:
        return []

    today = date.today()
    past_employer_set, past_lump_schedule = _classify_entries(parsed, today)
    month_info = _build_month_timeline(parsed, past_employer_set, today)
    entry_data = _init_entry_accumulators(parsed, past_employer_set)

    balance = _walk_timeline(
        parsed, month_info, past_employer_set, past_lump_schedule, entry_data, today,
    )

    return _build_enriched_results(parsed, entry_data, past_employer_set, balance, today)


def resolve_epf_rate(start_date_str: str, end_date_str: str = "") -> float | None:
    """Compute the weighted-average EPFO rate for a date range.

    Used to fill in the interest rate when the user leaves it blank.
    Returns ``None`` if the start date cannot be parsed.
    """
    start = parse_date(start_date_str)
    if not start:
        return None
    end = parse_date(end_date_str) if end_date_str else None
    effective_end = end or date.today()
    if effective_end > date.today():
        effective_end = date.today()

    rate_sum = 0.0
    rate_count = 0
    for year, month in _month_range(start, effective_end):
        rate_sum += _get_epf_rate(year, month)
        rate_count += 1

    if rate_count == 0:
        return None
    return round(rate_sum / rate_count, 2)
