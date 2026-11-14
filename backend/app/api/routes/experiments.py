"""Browse / filter experiment records."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def list_experiments(fuel: str | None = None, platform: str | None = None):
    # TODO: query DB with filters
    return []


@router.get("/{experiment_id}")
def get_experiment(experiment_id: int):
    # TODO: fetch single record
    return {"id": experiment_id}
