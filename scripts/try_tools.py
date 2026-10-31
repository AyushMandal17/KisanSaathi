"""Inspect normalized ToolResult payloads; --live contacts public data APIs."""
import argparse
import asyncio
import json
import logging

from app.config import get_settings
from app.schemas import FarmerProfile
from app.tools.protocol import RealTools


async def run(live: bool):
    settings = get_settings()
    if live:
        settings = settings.model_copy(update={"data_mode": "live"})
    profile = FarmerProfile.model_validate(json.loads(
        (settings.data_dir / "seed_farmers.json").read_text(encoding="utf-8")
    )["farmers"][0])
    tools = RealTools(settings)
    results = await asyncio.gather(tools.weather(profile), tools.mandi(profile, profile.crops[0].crop),
                                   tools.crop_stage(profile, profile.crops[0].crop))
    for result in results:
        logging.info("%s", result.model_dump_json(indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(run(args.live))
