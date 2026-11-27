"""Real HA Core smoke test, isolated config directory and synthetic sources."""
import asyncio
import shutil
import tempfile
from pathlib import Path

from homeassistant import bootstrap, loader
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry, entity_registry

ATTRS = {"device_class": "pm25", "unit_of_measurement": "μg/m³"}
ROOT = Path(__file__).parents[1]


async def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        shutil.copytree(ROOT / "custom_components", root / "custom_components")
        hass = HomeAssistant(tmp)
        try:
            assert await bootstrap.async_from_config_dict({"homeassistant": {}, "sensor": []}, hass)
            integrations = await loader.async_get_custom_components(hass)
            assert "indoor_aqi" in integrations
            assert integrations["indoor_aqi"].config_flow
            registry = entity_registry.async_get(hass)
            area = area_registry.async_get(hass).async_create("Living room")
            source = registry.async_get_or_create("sensor", "test_fixture", "pm1", suggested_object_id="fixture_pm1")
            registry.async_update_entity(source.entity_id, area_id=area.id)
            hass.states.async_set(source.entity_id, "8", ATTRS)
            hass.states.async_set("sensor.fixture_pm2", "10", ATTRS)
            hass.states.async_set("sensor.fixture_pm3", "11", ATTRS)
            hass.states.async_set("sensor.fixture_pm4", "4", ATTRS)
            hass.states.async_set("sensor.not_pm25", "50", {"device_class":"pm10","unit_of_measurement":"μg/m³"})
            flow = await hass.config_entries.flow.async_init("indoor_aqi", context={"source":"user"})
            assert flow["type"] == "form", flow
            result = await hass.config_entries.flow.async_configure(flow["flow_id"], {})
            assert result["type"] == "create_entry", result
            await hass.async_block_till_done()
            entry = result["result"]
            assert entry.state.value == "loaded", entry.state

            def aqi_entities():
                return {e.unique_id: e for e in registry.entities.values() if e.platform == "indoor_aqi"}

            entities = aqi_entities()
            assert len(entities) == 6, entities
            def value(key):
                return hass.states.get(entities[key].entity_id).state
            assert value("source_" + source.id) == "44"
            assert entities["source_" + source.id].area_id == area.id
            assert value("indoor_average") == "44"
            assert value("indoor_maximum") == "55"
            hass.states.async_set(source.entity_id, "unavailable", ATTRS)
            await hass.async_block_till_done()
            assert value("source_" + source.id) == "unavailable"
            assert value("indoor_average") == "43"
            hass.states.async_set(source.entity_id, "0", ATTRS)
            await hass.async_block_till_done()
            assert value("source_" + source.id) == "0"
            assert value("indoor_average") == "33"
            assert await hass.config_entries.async_unload(entry.entry_id)
            await hass.async_block_till_done()
            assert all(hass.states.get(e.entity_id) is None for e in entities.values())
            print("Real HA smoke test passed: discovery, UI config flow, six sensors, area, updates, unavailable, unload")
        finally:
            await hass.async_stop(force=True)


if __name__ == "__main__":
    asyncio.run(main())
