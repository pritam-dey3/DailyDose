# Selection Algorithm

## Selection

The selection process uses a **Dynamic Urgency Auction** model. Instead of rigid phases or pre-planning, every potential dose competes for a slot daily based on a score that rises over time.

1.  **Metric Application (The "Pressure")**
    For every digest, the system calculates an **Urgency Score** for every active dose in the library.
    - **Time Pressure (T):** The primary unit of pressure is **Days**. For flexible frequencies, the score increases linearly over time since last shown.
    - **Demand (D):** Derived from tag configuration. This acts as a multiplier on time, determining how fast a dose "ages" relative to wall-clock time.
      - $D = 1.0$: Standard aging (1 day of pressure).
      - $D > 1.0$: High importance. The item appears to age faster than real time, accumulating pressure quickly (e.g., $D=2$ means 1 day feels like 2 days).
      - $D < 1.0$: Low importance. The item ages slowly, being surpassed by standard items (e.g., $D=0.5$ means 2 days feel like 1 day).
    - **Quota Pressure (Q):** If a dose has a hard constraint (e.g., `at-least 3/week`) and the deadline is approaching, the score skyrockets.
      $$\frac{\text{1 }}{\text{digests remaining} - \text{doses remaining}}$$
      - _Critical Fix:_ If `doses remaining` >= `digests remaining` (the user is behind schedule), $Q$ becomes $\infty$. This prevents the logic inversion where missed deadlines yield negative numbers.

    Final pressure $P = (T \cdot D) + \alpha\cdot Q$. Where $\alpha$ is a user-configurable constant. Users tune this to determine how aggressively "behind schedule" items displace "high interest" items (balancing Quota catch-up vs. regular browsing).

2.  **The Auction (Selection)**
    - **Priority Selection:** All doses with $\infty$ score (due to unmet quotas or overdue status) are automatically selected first.
      - _Slot Overload Policy:_ If the number of infinite items exceeds the daily slot limit, the limit is explicitly ignored, and **all** infinite items are sent. This "digest overflow" is intentional behavior designed to signal to the user that their configured quotas exceed their available daily capacity.
    - **Weighted Sampling:** Any remaining slots are filled by **Weighted Random Sampling** of the Urgency Scores.

3.  **The Relief (Reset)**
    - Selected doses have their "pressure" released. Their `count_in_current_period` increments, and doses remaining counters decrement. This allows them to re-enter the auction cycle later with fresh urgency.
    - Unselected doses keep their pressure, making them more likely to "win" the auction tomorrow.

4.  **Initialization & Configuration**
    - **Week Cycle:** The week is fixed as **Sunday to Saturday**.
    - **New Items:** When a new dose is added in the middle of a week, its `count_in_current_period` value is initialized based on user preference:
      - Option A: `0` (starts fresh).
      - Option B: `random(0, n)` (simulates history to stagger new items entering the pool).
    - **Quota Proration:** Quotas are **not** prorated for items added mid-week. If a "3/week" item is added on Friday, the system will attempt to fulfill the entire quota in the remaining days. This is by design.

_Goal:_ This system naturally balances high-frequency habits (which build pressure fast) with low-frequency interests (which build pressure slowly), without needing complex "if-then" Phase 1/Phase 2 logic.
