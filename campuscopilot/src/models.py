"""
models.py
---------
Domain model classes for CampusCopilot.

WHY THIS MODULE EXISTS:
We use Object-Oriented Programming (OOP) instead of raw dictionaries because:
1. Encapsulation -> data + behavior together, easier to reason about.
2. Type-safety  -> attributes are named, IDEs autocomplete, bugs caught early.
3. Reusability  -> other modules import these classes rather than juggling
                   raw DataFrame columns.

Q&A defense:
"Why classes instead of dictionaries?" -> Dictionaries have no schema; a typo
in a key fails silently. Classes enforce structure and make the code
self-documenting. They also let us add domain methods (e.g. Event.conflicts_with).
"""

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import List


# -----------------------------------------------------------------------------
# @dataclass is a Python decorator (PEP 557) that auto-generates __init__,
# __repr__, and __eq__ for us. Cleaner than writing boilerplate.
# "frozen=True" would make it immutable; we leave it mutable so Students can
# update their fees paid.
# -----------------------------------------------------------------------------
@dataclass
class Student:
    """Represents a single university student."""
    student_id: str
    name: str
    department: str
    year: int
    fees_paid: float
    fees_due: float

    @property
    def total_fees(self) -> float:
        """Computed property -> never stored, always derived. Avoids stale data."""
        return self.fees_paid + self.fees_due

    @property
    def is_defaulter(self) -> bool:
        """Returns True if the student still owes fees."""
        return self.fees_due > 0


@dataclass
class Event:
    """Represents a single campus event.

    Used by:
      - Greedy Activity Selection (to pick max non-overlapping events).
      - 0/1 Knapsack             (to pick events that maximise student reach
                                   within a sponsor budget).
    """
    event_id: str
    name: str
    date: datetime
    start_time: time
    end_time: time
    location: str
    department: str
    cost: int             # rupees; used as "weight" in knapsack
    students_reached: int # used as "value"  in knapsack
    latitude: float
    longitude: float

    def conflicts_with(self, other: "Event") -> bool:
        """
        Two events conflict iff they are on the SAME date AND their time
        intervals overlap.

        Why this method lives on Event and not on the scheduler:
        -> The rule "what counts as a conflict" is a property of events
           themselves; the scheduler just asks the question.
        """
        if self.date.date() != other.date.date():
            return False
        # Standard interval-overlap check: A.start < B.end AND B.start < A.end.
        return self.start_time < other.end_time and other.start_time < self.end_time


@dataclass
class Department:
    """Represents a department with aggregated finance numbers."""
    name: str
    total_expense: float = 0.0
    total_budget: float = 0.0
    # field(default_factory=list) is the correct way to give a mutable default.
    # Using "[]" directly would share the SAME list across all instances -- classic Python bug.
    monthly_expenses: List[float] = field(default_factory=list)

    @property
    def utilization(self) -> float:
        """What % of the budget has been spent. Guards against div-by-zero."""
        if self.total_budget == 0:
            return 0.0
        return (self.total_expense / self.total_budget) * 100

    @property
    def is_over_budget(self) -> bool:
        return self.total_expense > self.total_budget
