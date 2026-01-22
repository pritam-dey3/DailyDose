from sqlmodel import Session, SQLModel, create_engine

from src.db.models import Dose, FrequencyPeriod, FrequencyType, Tag
from src.settings import settings


def init_db():
    engine = create_engine(settings.db_url)
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        # Create Tags
        tags = [
            Tag(name="exercise", demand=1.5),
            Tag(name="nutrition", demand=1.2),
            Tag(name="finance", demand=0.5),
        ]
        session.add_all(tags)

        # Create Doses
        doses = [
            Dose(
                id="complex_movement",
                tag_name="exercise",
                frequency_type=FrequencyType.AT_LEAST,
                frequency_count=1,
                frequency_period=FrequencyPeriod.DAY,
                message="Do a compound movement today (Squat, Deadlift, or Bench).",
            ),
            Dose(
                id="walk_10k",
                tag_name="exercise",
                frequency_type=FrequencyType.AT_LEAST,
                frequency_count=3,
                frequency_period=FrequencyPeriod.WEEK,
                message="Go for a long walk aiming for 10k steps.",
            ),
            Dose(
                id="drink_water",
                tag_name="nutrition",
                frequency_type=FrequencyType.AT_LEAST,
                frequency_count=1,
                frequency_period=FrequencyPeriod.DAY,
                message="Drink 8 glasses of water.",
            ),
            Dose(
                id="check_balance",
                tag_name="finance",
                frequency_type=FrequencyType.EXACTLY,
                frequency_count=1,
                frequency_period=FrequencyPeriod.MONTH,
                message="Review your monthly expenses.",
            ),
        ]
        session.add_all(doses)
        session.commit()
        print("Initialized database with initial data.")


if __name__ == "__main__":
    init_db()
