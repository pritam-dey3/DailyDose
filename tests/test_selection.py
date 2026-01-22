from datetime import datetime, timedelta

import pytest
from sqlmodel import Session, SQLModel, create_engine

from src.db.models import Dose, FrequencyPeriod, FrequencyType, History, Tag
from src.selection import (
    calculate_urgency_score,
    generate_daily_digest,
    get_days_remaining_in_week,
    select_doses,
)


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


def create_history(dose_id="1", count=0):
    return History(dose_id=dose_id, count_in_current_period=count)


def test_get_days_remaining_in_week():
    # Monday = 0. Rem = 6 (Mon-Sat incl)
    # Sat = 5. Rem = 1.
    # Sun = 6. Rem = 7.

    # Monday
    d = datetime(2023, 10, 23)  # Monday
    assert d.weekday() == 0
    assert get_days_remaining_in_week(d) == 6

    # Saturday
    d = datetime(2023, 10, 28)  # Saturday
    assert d.weekday() == 5
    assert get_days_remaining_in_week(d) == 1

    # Sunday
    d = datetime(2023, 10, 29)  # Sunday
    assert d.weekday() == 6
    assert get_days_remaining_in_week(d) == 7


def test_urgency_score_time_pressure():
    dose = create_dose()
    tag = create_tag(demand=1.0)
    current_date = datetime(2023, 10, 25)  # Wed

    # Never shown -> T=0
    score, is_inf = calculate_urgency_score(dose, None, tag, current_date, alpha=1.0)
    # T=0, D=1. Q?
    # default dose: at least 1/week.
    # Wed -> Rem = 4 days.
    # Doses rem = 1.
    # Q = 1 / (4 - 1) = 0.333
    # P = 0*1 + 1*0.333 = 0.333
    assert not is_inf
    assert score == pytest.approx(0.333, 0.01)

    # Shown 2 days ago
    last = current_date - timedelta(days=2)
    history = create_history(count=0)  # last_notified removed, so count matters or not
    # T=0 (was 2). D=1. Q=0.333
    score, is_inf = calculate_urgency_score(dose, history, tag, current_date, alpha=1.0)
    # P = 0*1 + 0.333 = 0.333
    assert score == pytest.approx(0.333, 0.01)


def test_urgency_score_demand_multiplier():
    dose = create_dose()
    tag = create_tag(demand=2.0)  # High demand
    current_date = datetime(2023, 10, 25)
    last = current_date - timedelta(days=2)
    # history = create_history(last_notified=last)

    # T=0 (was 2). D=2. T*D = 0.
    # Q = 0.333
    history = create_history(count=0)
    score, _ = calculate_urgency_score(dose, history, tag, current_date, alpha=1.0)
    assert score == pytest.approx(0.333, 0.01)


def test_urgency_score_quota_infinite():
    # At least 3/week.
    # Today is Friday (rem=2: Fri, Sat).
    # current count=0. doses_rem=3.
    # doses_rem (3) >= digests_rem (2) -> Infinite

    dose = create_dose(freq_count=3)
    tag = create_tag()
    current_date = datetime(2023, 10, 27)  # Friday
    assert get_days_remaining_in_week(current_date) == 2

    score, is_inf = calculate_urgency_score(dose, None, tag, current_date, alpha=1.0)
    assert is_inf
    assert score == float("inf")


def test_urgency_score_quota_met():
    dose = create_dose(freq_count=1)
    tag = create_tag()
    history = create_history(count=1)
    current_date = datetime(2023, 10, 23)

    score, is_inf = calculate_urgency_score(dose, history, tag, current_date, alpha=1.0)
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
    # Rem days <= 7. Infinite.

    doses_data = [(d1, None, tag), (d2, None, tag), (d3, None, tag)]

    selected = select_doses(doses_data, datetime.now(), digest_size=2)
    assert len(selected) == 3
    assert set(d.id for d in selected) == {"1", "2", "3"}


def test_auction_weighted_sampling():
    # 1 priority, 2 normal slots left (size 3).
    # Normal items with different scores.

    # Inf
    d1 = create_dose(id="1", freq_count=10)

    # Normal
    d2 = create_dose(id="2")  # Score low
    d3 = create_dose(id="3")  # Score high

    t_normal = create_tag(demand=1.0)
    current_date = datetime(2023, 10, 25)  # Wed

    # d2: T=0
    h2 = create_history(dose_id="2", count=0)
    # d3: T=0
    h3 = create_history(dose_id="3", count=0)

    doses_data = [(d1, None, t_normal), (d2, h2, t_normal), (d3, h3, t_normal)]

    # Repeat many times to check if d3 is picked more often than d2 theoretically,
    # but here we just check if selection works.

    selected = select_doses(doses_data, current_date, digest_size=2)

    # Must include d1
    assert any(d.id == "1" for d in selected)
    # Size 2
    assert len(selected) == 2


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
        # assert hist.last_notified == current_date # Removed
