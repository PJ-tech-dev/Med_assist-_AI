import asyncio
import sys
import os

from app.agents.map_agent import MapAgent
from app.core.settings import settings

async def main():
    print(f"API KEY: {settings.gemini_maps_api_key}")
    agent = MapAgent()
    res = await agent.fetch_pharmacies_gemini(10.83, 77.07, "Pollachi")
    print("PHARMACIES:", res)

if __name__ == "__main__":
    asyncio.run(main())
