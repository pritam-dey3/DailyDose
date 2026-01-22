from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class FrequencyType(str, Enum):
    AT_LEAST = "at-least"
    EXACTLY = "exactly"


class FrequencyPeriod(str, Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class Tag(SQLModel, table=True):
    __tablename__ = "tags"  # type: ignore

    name: str = Field(primary_key=True)
    demand: float


class Dose(SQLModel, table=True):
    __tablename__ = "doses"  # type: ignore

    id: str = Field(primary_key=True)
    tag_name: str = Field(foreign_key="tags.name")

    # Frequency
    frequency_type: FrequencyType
    frequency_count: int
    frequency_period: FrequencyPeriod

    message: str


class History(SQLModel, table=True):
    __tablename__ = "history"  # type: ignore

    dose_id: str = Field(primary_key=True, foreign_key="doses.id")
    count_in_current_period: int = Field(default=0)
