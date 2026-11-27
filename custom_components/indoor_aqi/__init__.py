"""Local, read-only indoor AQI integration."""
from homeassistant.const import Platform

DOMAIN = "indoor_aqi"
PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass, entry):
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
