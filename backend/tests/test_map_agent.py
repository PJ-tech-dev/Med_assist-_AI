import pytest
from app.agents.map_agent import MapAgent
from app.core.settings import settings

@pytest.mark.asyncio
async def test_map_agent_fetch():
    # Only test if api key is present
    if not settings.gemini_maps_api_key:
        pytest.skip("GEMINI_MAPS_API_KEY not set")
    
    agent = MapAgent()
    # Test coordinates for Chennai (13.0827, 80.2707)
    res = await agent.process_location_query(13.0827, 80.2707, "Find some pharmacies")
    
    assert "location" in res
    assert "pharmacies" in res
    assert "summary" in res
    assert len(res["pharmacies"]) > 0
    assert "lat" in res["location"]
    
@pytest.mark.asyncio
async def test_map_agent_fetch_no_query():
    if not settings.gemini_maps_api_key:
        pytest.skip("GEMINI_MAPS_API_KEY not set")
        
    agent = MapAgent()
    res = await agent.process_location_query(13.0827, 80.2707)
    
    assert "location" in res
    assert "pharmacies" in res
    assert "summary" in res
    assert len(res["pharmacies"]) > 0
