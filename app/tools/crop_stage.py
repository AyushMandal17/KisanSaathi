"""Calendar estimates, never an observation of a farmer's crop."""
from __future__ import annotations

from datetime import datetime
from typing import Callable
from zoneinfo import ZoneInfo

import yaml

from app.schemas import FarmerProfile, ToolResult
from app.tools.cache import utcnow


class CropStageTool:
    def __init__(self, settings, clock: Callable[[], datetime] = utcnow):
        self.settings, self.clock = settings, clock

    async def fetch(self, profile: FarmerProfile, crop: str) -> ToolResult:
        now = self.clock()
        try:
            configuration = yaml.safe_load(self.settings.crops_path.read_text(encoding="utf-8"))
            calendar = configuration["crops"].get(crop.casefold())
            plots = [plot for plot in profile.crops if plot.crop.casefold() == crop.casefold()]
            if len(plots) != 1:
                raise ValueError("Crop plot missing or ambiguous; record one sowing date per crop.")
            if not calendar:
                raise ValueError("No crop calendar configured for this crop.")
            days = (now.astimezone(ZoneInfo("Asia/Kolkata")).date() - plots[0].sowing_date).days
            if days < 0:
                raise ValueError("Sowing date is in the future; stage cannot be estimated.")
            stage = next((stage for stage in calendar["stages"]
                          if stage["min_days"] <= days <= stage["max_days"]), None)
            if stage is None:
                raise ValueError("Sowing date falls outside the configured crop calendar.")
            return ToolResult(
                tool="crop_stage", source=calendar["source"], fetched_at=now, confidence="medium",
                value={"crop": crop, "stage": stage["name"], "stage_hi": stage["hi"],
                       "days_since_sowing": days, "sowing_date": plots[0].sowing_date.isoformat(),
                       "estimated": True, "calendar_status": calendar["status"],
                       "data_gaps": ["Variety, field observations and soil moisture are not recorded."]},
            )
        except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as exc:
            message = str(exc) if isinstance(exc, ValueError) else "Crop calendar unavailable"
            return ToolResult(tool="crop_stage", source="Configured crop calendar (estimated)",
                              fetched_at=now, error=message)
