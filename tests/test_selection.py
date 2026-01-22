import math
from datetime import datetime, timedelta

import pytest
from sqlmodel import Session, SQLModel, create_engine

from src.db.models import Dose, FrequencyPeriod, FrequencyType, History, Tag
from src.selection import (
    calculate_urgency_score,
    generate_daily_digest,
    get_digests_remaining_in_period,
    select_doses,
)

TIMINGS_1_PER_DAY = ["12:00"]


# Helper to create objects
def create_dose(
    id="1",
    freq_type=FrequencyType.AT_LEAST,
    freq_count=1,
    freq_period=FrequencyPeriod.WEEK,
    tag_name="test",
):
    return Dose(
        id=id,
        tag_name=tag_name,
        frequency_type=freq_type,
        frequency_count=freq_count,
        frequency_period=freq_period,
        message="msg",
    )


def create_tag(name="test", demand=1.0):
    return Tag(name=name, demand=demand)


def create_history(dose_id="1", count=0, last_digest_datetime=None):
    return History(
        dose_id=dose_id,
        count_in_current_period=count,
        last_digest_datetime=last_digest_datetime,
    )


def test_get_digests_remaining_in_period():
    # Digest timings: ["08:00", "12:00", "18:00"] (3 per day)
    timings = ["08:00", "12:00", "18:00"]

    # Case Day
    # Morning 07:00. 3 remaining.
    d = datetime(2023, 10, 23, 7, 0)
    assert get_digests_remaining_in_period(d, FrequencyPeriod.DAY, timings) == 3

    # Noon 13:00. 1 remaining (18:00).
    d = datetime(2023, 10, 23, 13, 0)
    assert get_digests_remaining_in_period(d, FrequencyPeriod.DAY, timings) == 1

    # Case Week
    # Monday 07:00.
    # Today: 3.
    # Future: Tue, Wed, Thu, Fri, Sat (5 days). 5 * 3 = 15.
    # Total: 18.
    d = datetime(2023, 10, 23, 7, 0)  # Monday
    assert d.weekday() == 0
    assert get_digests_remaining_in_period(d, FrequencyPeriod.WEEK, timings) == 18

    # Saturday 13:00.
    # Today: 1 (18:00).
    # Future: 0.
    # Total: 1.
    d = datetime(2023, 10, 28, 13, 0)  # Saturday
    assert d.weekday() == 5
    assert get_digests_remaining_in_period(d, FrequencyPeriod.WEEK, timings) == 1

    # Case Month
    # Oct 25 (Wed). Month ends Oct 31 (Tue).
    # Today (Oct 25, 07:00): 3.
    # Future days: Oct 31 - Oct 25 = 6 days (26, 27, 28, 29, 30, 31).
    # 6 * 3 = 18.
    # Total: 21.
    d = datetime(2023, 10, 25, 7, 0)
    assert get_digests_remaining_in_period(d, FrequencyPeriod.MONTH, timings) == 21


def test_urgency_score_time_pressure():
    dose = create_dose()
    tag = create_tag(demand=1.0)
    current_date = datetime(2023, 10, 25)  # Wed

    # Never shown -> T=0
    score = calculate_urgency_score(
        dose, None, tag, current_date, alpha=1.0, digest_timings=TIMINGS_1_PER_DAY
    )
    is_inf = math.isinf(score)
    # T=0, D=1. Q?
    # default dose: at least 1/week.
    # Wed -> Rem = 4 slots (using TIMINGS_1_PER_DAY).
    # Doses rem = 1.
    # Q = 1 / (4 - 1) = 0.333
    # P = 0*1 + 1*0.333 = 0.333
    assert not is_inf
    assert score == pytest.approx(0.333, 0.01)

    # Shown 2 days ago
    last_shown = current_date - timedelta(days=2)
    history = create_history(count=0, last_digest_datetime=last_shown)
    # T=2. D=1. T*D = 2.
    # Q=0.333
    # P = 2 + 0.333 = 2.333
    score = calculate_urgency_score(
        dose, history, tag, current_date, alpha=1.0, digest_timings=TIMINGS_1_PER_DAY
    )
    is_inf = math.isinf(score)
    assert not is_inf
    assert score == pytest.approx(2.333, 0.01)


def test_urgency_score_demand_multiplier():
    dose = create_dose()
    tag = create_tag(demand=2.0)  # High demand
    current_date = datetime(2023, 10, 25)

    # Time pressure ensures demand multiplier has an effect
    # T=2 days. D=2. T*D = 4.
    last_shown = current_date - timedelta(days=2)
    history = create_history(count=0, last_digest_datetime=last_shown)

    # Calculate expected Quota pressure
    # Wed -> Rem = 4 slots (using TIMINGS_1_PER_DAY).
    # Doses rem = 1.
    # Q = 1 / (4 - 1) = 0.333
    # P = (2 * 2) + (1.0 * 0.333) = 4.333

    score = calculate_urgency_score(
        dose, history, tag, current_date, alpha=1.0, digest_timings=TIMINGS_1_PER_DAY
    )
    assert score == pytest.approx(4.333, 0.01)


def test_urgency_score_quota_infinite():
    # At least 3/week.
    # Today is Friday (rem=2: Fri, Sat with 1 slot each).
    # current count=0. doses_rem=3.
    # doses_rem (3) >= digests_rem (2) -> Infinite

    dose = create_dose(freq_count=3)
    tag = create_tag()
    current_date = datetime(2023, 10, 27)  # Friday
    # assert get_days_remaining_in_week(current_date) == 2

    score = calculate_urgency_score(
        dose, None, tag, current_date, alpha=1.0, digest_timings=TIMINGS_1_PER_DAY
    )
    is_inf = math.isinf(score)
    assert is_inf
    assert score == float("inf")


def test_urgency_score_quota_met():
    dose = create_dose(freq_count=1)
    tag = create_tag()
    history = create_history(count=1)
    current_date = datetime(2023, 10, 23)

    score = calculate_urgency_score(
        dose, history, tag, current_date, alpha=1.0, digest_timings=TIMINGS_1_PER_DAY
    )
    is_inf = math.isinf(score)
    # doses_rem = 0. Q=0.
    # T=0 (if last_notified is None or long ago, let's assume None -> T=0)
    # P = 0.
    assert not is_inf
    assert score == 0.0


def test_auction_priority_overflow():
    # 3 infinite items, digest size 2.
    # Should return all 3.

    d1 = create_dose(id="1", freq_count=10)  # Impossible quota
    d2 = create_dose(id="2", freq_count=10)
    d3 = create_dose(id="3", freq_count=10)

    tag = create_tag()
    # No history -> count 0 -> remaining 10.

    # Use fixed date Saturday with 1 slot/day -> 1 remaining.
    current_date = datetime(2023, 10, 28, 10, 0)  # Saturday
    timings = ["12:00"]  # 1 per day

    doses_data = [(d1, None, tag), (d2, None, tag), (d3, None, tag)]

    selected = select_doses(
        doses_data, current_date, digest_size=2, digest_timings=timings
    )
    assert len(selected) == 3
    assert set(d.id for d in selected) == {"1", "2", "3"}


def test_auction_weighted_sampling():
    # 1 priority, 2 normal slots left (size 3).
    # Normal items with different scores.

    # Priority Item (Infinite Score due to quota overflow)
    d_priority = create_dose(id="1", freq_count=10)

    # Normal Items
    d_low = create_dose(id="low", tag_name="low_demand")
    d_high = create_dose(id="high", tag_name="high_demand")

    tag_low = create_tag(name="low_demand", demand=1.0)
    tag_high = create_tag(name="high_demand", demand=10.0)  # High multiplier

    current_date = datetime(2023, 10, 25)  # Wed

    # Give both some time pressure so demand multiplier works
    last_shown = current_date - timedelta(days=2)
    h_low = create_history(dose_id="low", count=0, last_digest_datetime=last_shown)
    h_high = create_history(dose_id="high", count=0, last_digest_datetime=last_shown)

    # Ensure scores are significantly different
    # Low: T=2, D=1 => P ~ 2 + Q
    # High: T=2, D=10 => P ~ 20 + Q
    score_low = calculate_urgency_score(
        d_low, h_low, tag_low, current_date, 1.0, TIMINGS_1_PER_DAY
    )
    score_high = calculate_urgency_score(
        d_high, h_high, tag_high, current_date, 1.0, TIMINGS_1_PER_DAY
    )
    assert score_high > score_low * 2

    doses_data = [
        (d_priority, None, tag_low),
        (d_low, h_low, tag_low),
        (d_high, h_high, tag_high),
    ]

    # Sample multiple times to verify bias
    # We have 2 slots. 1 is taken by priority. 1 left for normal.
    # We expect d_high to be picked significantly more often than d_low.

    high_wins = 0
    low_wins = 0
    iterations = 100

    for _ in range(iterations):
        selected = select_doses(
            doses_data, current_date, digest_size=2, digest_timings=TIMINGS_1_PER_DAY
        )

        # Priority should always be there
        selected_ids = [d.id for d in selected]
        assert "1" in selected_ids

        if "high" in selected_ids:
            high_wins += 1
        if "low" in selected_ids:
            low_wins += 1

    # Check that high score item prevailed efficiently
    # Given the scores, high should win vast majority
    assert high_wins > low_wins
    # Being conservative with randomness, but 10x demand should result in heavy bias
    assert high_wins > 60


def test_integration_db_update():
    # Setup in-memory DB
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        tag = create_tag()
        session.add(tag)
        d1 = create_dose(id="1")
        session.add(d1)
        session.commit()

        current_date = datetime(2023, 10, 25)

        # Select
        selected = generate_daily_digest(session, current_date)

        assert len(selected) == 1
        assert selected[0].id == "1"

        # Check history updated
        hist = session.get(History, "1")
        assert hist is not None
        assert hist.count_in_current_period == 1
        assert hist.last_digest_datetime == current_date
