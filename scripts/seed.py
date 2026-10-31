"""Idempotent insert-only demo seed; existing profiles are retained."""
import json
import logging

from app.config import get_settings
from app.db import create_database
from app.repository import FarmerRepository
from app.schemas import FarmerProfile


def seed() -> int:
    settings = get_settings()
    engine, factory = create_database(settings)
    payload = json.loads((settings.data_dir / "seed_farmers.json").read_text(encoding="utf-8"))
    added = 0
    with factory() as session:
        repository = FarmerRepository(session)
        for entry in payload["farmers"]:
            profile = FarmerProfile.model_validate(entry)
            if repository.get(profile.farmer_id) is None:
                repository.create(profile)
                added += 1
    engine.dispose()
    logging.getLogger(__name__).info("Seed complete: %d DEMO profiles inserted", added)
    return added


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    seed()
