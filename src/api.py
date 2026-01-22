from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from src.db import get_session
from src.db.models import Dose, FrequencyPeriod, FrequencyType, Tag
from src.settings import settings

app = FastAPI(root_path=settings.root_path)


@app.get("/health")
def health_check():
    return "OK"


@app.get("/doses")
def get_doses(session: Session = Depends(get_session)):
    doses = session.exec(select(Dose)).all()
    return doses


@app.get("/doses/{id}")
def get_dose(id: str, session: Session = Depends(get_session)):
    dose = session.get(Dose, id)
    if not dose:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dose not found"
        )
    return dose


class DoseBody(BaseModel):
    id: str
    tag_name: str
    message: str
    frequency_type: FrequencyType
    frequency_count: int
    frequency_period: FrequencyPeriod


@app.post("/doses", status_code=status.HTTP_201_CREATED)
def create_dose(dose_body: DoseBody, session: Session = Depends(get_session)):
    # Check if dose already exists
    existing_dose = session.get(Dose, dose_body.id)
    if existing_dose:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dose with this ID already exists",
        )
    tag = session.get(Tag, dose_body.tag_name)
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tag '{dose_body.tag_name}' does not exist",
        )

    dose = Dose.model_validate(dose_body)
    session.add(dose)
    session.commit()
    session.refresh(dose)
    return dose


class TagBody(BaseModel):
    name: str
    demand: Annotated[float, Field(gt=0)]


@app.get("/tags")
def get_tags(session: Session = Depends(get_session)):
    tags = session.exec(select(Tag)).all()
    return tags


@app.get("/tags/{tag_name}")
def get_tag(tag_name: str, session: Session = Depends(get_session)):
    tag = session.get(Tag, tag_name)
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found"
        )
    return tag


@app.post("/tags", status_code=status.HTTP_201_CREATED)
def create_tag(tag_body: TagBody, session: Session = Depends(get_session)):
    existing_tag = session.get(Tag, tag_body.name)
    if existing_tag:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tag with this name already exists",
        )
    tag = Tag.model_validate(tag_body)
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return tag
