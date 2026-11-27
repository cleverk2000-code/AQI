"""UI-only installation; no configuration.yaml or credentials."""
from homeassistant import config_entries


class IndoorAQIConfigFlow(config_entries.ConfigFlow, domain="indoor_aqi"):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id("indoor_aqi")
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title="Indoor AQI", data={})
        return self.async_show_form(step_id="user")
