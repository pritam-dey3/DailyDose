import calendar
import math
import random
from collections.abc import Sequence
from datetime import datetime

from sqlmodel import Session, select

from src.db.models import Dose, FrequencyPeriod, History, Tag
from src.settings import settings


def get_digests_remaining_in_period(
    current_datetime: datetime, period: FrequencyPeriod, digest_timings: list[str]
) -> int:
    """
    Returns the number of digest opportunities remaining in the frequency period.
    """
    # 1. Calculate remaining digests today
    current_time_str = current_datetime.strftime("%H:%M")
    remaining_today = sum(1 for t in digest_timings if t > current_time_str)

    daily_slots = len(digest_timings)

    if period == FrequencyPeriod.DAY:
        return remaining_today

    elif period == FrequencyPeriod.WEEK:
        # Week ends on Saturday.
        wd = current_datetime.weekday()  # Mon=0, ..., Sat=5, Sun=6

        days_in_week_including_today = 7 if wd == 6 else (6 - wd)
        future_days = days_in_week_including_today - 1
        return remaining_today + (future_days * daily_slots)

    elif period == FrequencyPeriod.MONTH:
        # Days remaining in month
        _, last_day = calendar.monthrange(current_datetime.year, current_datetime.month)
        future_days = last_day - current_datetime.day
        return remaining_today + (future_days * daily_slots)

    else:
        raise ValueError(f"Unknown FrequencyPeriod: {period}")


def calculate_urgency_score(
    dose: Dose,
    history: History | None,
    tag: Tag,
    current_date: datetime,
    alpha: float,
    digest_timings: list[str],
) -> float:
    """
    Calculates the urgency score for a dose.
    Returns score.
    """
    # 1. Time Pressure (T)
    T = 0.0
    if history and history.last_digest_datetime:
        # Calculate days elapsed
        delta = current_date.date() - history.last_digest_datetime.date()
        T = max(0.0, float(delta.days))

    # 2. Demand (D)
    D = tag.demand

    # 3. Quota Pressure (Q)
    digests_remaining = get_digests_remaining_in_period(
        current_date, dose.frequency_period, digest_timings
    )

    current_count = history.count_in_current_period if history else 0
    doses_remaining = dose.frequency_count - current_count

    if doses_remaining <= 0:
        Q = 0.0  # Quota met
    else:
        if doses_remaining >= digests_remaining:
            Q = float("inf")
        else:
            Q = 1.0 / (digests_remaining - doses_remaining)

    # Final Pressure P
    P = (T * D) + (alpha * Q)

    return P


def select_doses(
    doses_data: Sequence[tuple[Dose, History | None, Tag]],
    current_date: datetime,
    settings_alpha: float = 10.0,
    digest_size: int = 5,
    digest_timings: list[str] | None = None,
) -> list[Dose]:
    """
    Performs the auction and selection.
    """
    if digest_timings is None:
        digest_timings = settings.selection.digest_timings

    # 1. Metric Application
    scored_items = []
    for dose, history, tag in doses_data:
        score = calculate_urgency_score(
            dose, history, tag, current_date, settings_alpha, digest_timings
        )
        scored_items.append({
            "dose": dose,
            "score": score,
            "is_infinite": math.isinf(score),
        })

    # 2. The Auction
    priority_items = [item for item in scored_items if item["is_infinite"]]
    normal_items = [item for item in scored_items if not item["is_infinite"]]

    selected_doses = []

    # Priority Selection
    # Slot Overload Policy: If infinite items > limit, ignore limit and send ALL.
    if len(priority_items) > digest_size:
        return [item["dose"] for item in priority_items]

    selected_doses.extend([item["dose"] for item in priority_items])
    remaining_slots = digest_size - len(selected_doses)

    # Weighted Sampling
    if remaining_slots > 0 and normal_items:
        # Filter out 0 scores or negative? Spec says "score that rises".
        # If score is 0, probability is 0.
        # Weighted random sampling.
        weights = [max(0, item["score"]) for item in normal_items]
        candidates = [item["dose"] for item in normal_items]

        # If all weights are 0, we can't sample based on weights.
        # Either pick random or none.
        if sum(weights) == 0:
            # Fallback: Random sample if any candidates? Or just pick none?
            # If pressure is 0, maybe they shouldn't be picked.
            # But "Option A: 0 (starts fresh)". If everything is fresh, nothing gets picked?
            # That seems wrong. Randomly pick if all 0?
            if len(candidates) > 0:
                # Pick uniformly
                chosen = random.sample(
                    candidates, k=min(remaining_slots, len(candidates))
                )
                selected_doses.extend(chosen)
        else:
            # random.choices is with replacement. We want without replacement.
            # Using weights.
            # Implementation of weighted sample without replacement:
            # Easiest: Use numpy.random.choice(replace=False).
            # But we might not want numpy dependency.
            # Algorithm: A-Res, or repeated extraction.
            # Since N is small, we can just do repeated extraction.

            chosen = []
            available_items = list(zip(candidates, weights))

            for _ in range(remaining_slots):
                if not available_items:
                    break

                total_weight = sum(w for _, w in available_items)
                if total_weight == 0:
                    # Remainder uniform
                    items_left = [i for i, _ in available_items]
                    chosen.extend(
                        random.sample(
                            items_left,
                            k=min(len(items_left), remaining_slots - len(chosen)),
                        )
                    )
                    break

                r = random.uniform(0, total_weight)
                upto = 0
                for i, (dose, w) in enumerate(available_items):
                    if upto + w >= r:
                        chosen.append(dose)
                        available_items.pop(i)
                        break
                    upto += w

            selected_doses.extend(chosen)

    return selected_doses


def generate_daily_digest(
    session: Session, current_date: datetime = datetime.now()
) -> list[Dose]:
    # Fetch all active doses, history, tags
    # Join queries
    statement = select(Dose, History, Tag).outerjoin(History).join(Tag)
    results = session.exec(statement).all()  # List of (Dose, History | None, Tag)

    # Run selection
    selected_doses = select_doses(
        results,
        current_date,
        settings.selection.alpha,
        settings.selection.digest_size,
        settings.selection.digest_timings,
    )

    # 3. The Relief (Reset)
    for dose in selected_doses:
        # Get or create history
        history = session.get(History, dose.id)
        if not history:
            history = History(dose_id=dose.id, count_in_current_period=0)
            session.add(history)

        # Update last_digest_datetime
        history.last_digest_datetime = current_date

        # Update counters
        # Spec: "doses remaining counters decrement".
        # History stores "count_in_current_period".
        # So we increment count_in_current_period.
        history.count_in_current_period += 1

        session.add(history)

    session.commit()

    return selected_doses
