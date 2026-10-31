"""Small injected tool boundary shared by production orchestration and test fakes."""
from __future__ import annotations

from typing import Protocol

import httpx

from app.schemas import FarmerProfile, ToolResult
from app.tools.cache import ToolCache
from app.tools.crop_stage import CropStageTool
from app.tools.mandi import MandiTool
from app.tools.weather import WeatherTool


class Tools(Protocol):
    async def weather(self, profile: FarmerProfile) -> ToolResult:
        """Fetch a forecast using saved coordinates."""

    async def mandi(self, profile: FarmerProfile, crop: str) -> ToolResult:
        """Fetch matching market quotes with provenance."""

    async def crop_stage(self, profile: FarmerProfile, crop: str) -> ToolResult:
        """Estimate a crop stage from the saved sowing date."""


class RealTools:
    def __init__(self, settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self.data_mode, self.scenario = settings.data_mode, settings.demo_scenario
        cache = ToolCache(settings.cache_path)
        self.weather_tool = WeatherTool(settings, cache, client)
        self.mandi_tool = MandiTool(settings, cache, client)
        self.stage_tool = CropStageTool(settings)

    def set_scenario(self, scenario: str) -> None:
        if scenario not in {"rain", "dry", "heatwave", "api_failure", "stale_mandi", "no_mandi"}:
            raise ValueError("Unknown demo scenario")
        self.scenario = scenario

    async def weather(self, profile: FarmerProfile) -> ToolResult:
        if self.data_mode == "demo":
            return self.weather_tool.demo(self.scenario)
        return await self.weather_tool.fetch(profile)

    async def mandi(self, profile: FarmerProfile, crop: str) -> ToolResult:
        if self.data_mode == "demo":
            return self.mandi_tool.sample(profile, crop, scenario=self.scenario)
        return await self.mandi_tool.fetch(profile, crop)

    async def crop_stage(self, profile: FarmerProfile, crop: str) -> ToolResult:
        return await self.stage_tool.fetch(profile, crop)
