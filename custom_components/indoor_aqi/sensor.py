"""Discover PM2.5 sources and keep derived sensors synchronized."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import callback
from homeassistant.helpers import area_registry, device_registry, entity_registry
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval

from .calculation import calculate, category, is_pm25, summarize

SCAN_INTERVAL = timedelta(seconds=30)
METHOD = "EPA_2024_PM25_INSTANTANEOUS"


async def async_setup_entry(hass, entry, async_add_entities):
    manager = SourceManager(hass, async_add_entities)
    entry.async_on_unload(manager.stop)
    manager.start()


class SourceManager:
    """One subscription per live source, periodic discovery without global state listener."""

    def __init__(self, hass, add):
        self.hass = hass
        self.add = add
        self.registry = entity_registry.async_get(hass)
        self.devices = device_registry.async_get(hass)
        self.areas = area_registry.async_get(hass)
        self.sources = {}
        self.aggregates = (SummaryAQI(self, "average"), SummaryAQI(self, "maximum"))
        self.subscriptions = {}
        self.cancel_scan = None
        self.stopped = False

    @callback
    def start(self):
        self.add(list(self.aggregates))
        self.scan()
        self.cancel_scan = async_track_time_interval(self.hass, self.scan, SCAN_INTERVAL)

    @callback
    def stop(self):
        self.stopped = True
        if self.cancel_scan is not None:
            self.cancel_scan()
            self.cancel_scan = None
        for cancel in self.subscriptions.values():
            cancel()
        self.subscriptions.clear()

    def area_for(self, entity_id):
        entry = self.registry.async_get(entity_id)
        if entry is None:
            return None
        if entry.area_id:
            return entry.area_id
        device = self.devices.async_get(entry.device_id) if entry.device_id else None
        return device.area_id if device else None

    def label_for(self, state, entry):
        area_id = self.area_for(state.entity_id)
        area = self.areas.async_get_area(area_id) if area_id else None
        if area:
            return f"{area.name} AQI"
        if entry and entry.device_id:
            device = self.devices.async_get(entry.device_id)
            if device and (device.name_by_user or device.name):
                return f"{device.name_by_user or device.name} AQI"
        return f"{state.name} AQI"

    def source_value(self, source):
        entry = self.registry.async_get(source.source_id)
        if source.registry_id is not None and (entry is None or entry.id != source.registry_id):
            return None
        if entry and entry.disabled_by is not None:
            return None
        state = self.hass.states.get(source.source_id)
        if state is None or not is_pm25(
            state.attributes.get(ATTR_DEVICE_CLASS),
            state.attributes.get(ATTR_UNIT_OF_MEASUREMENT),
        ):
            return None
        return calculate(state.state)

    @callback
    def scan(self, now=None):
        if self.stopped:
            return
        found = set()
        for state in self.hass.states.async_all("sensor"):
            if not is_pm25(state.attributes.get(ATTR_DEVICE_CLASS),
                           state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)):
                continue
            entry = self.registry.async_get(state.entity_id)
            if entry and entry.disabled_by is not None:
                continue
            key = entry.id if entry else state.entity_id
            # If a formerly unregistered source gains a registry entry, retain its sensor.
            if key not in self.sources and state.entity_id in self.sources:
                key = state.entity_id
            found.add(key)
            source = self.sources.get(key)
            if source is None:
                source = RoomAQI(self, key, state.entity_id, self.label_for(state, entry), entry.id if entry else None)
                self.sources[key] = source
                self.add([source])
            elif source.source_id != state.entity_id:
                old_cancel = self.subscriptions.pop(key, None)
                if old_cancel:
                    old_cancel()
                source.source_id = state.entity_id
            if entry and source.registry_id is None:
                source.registry_id = entry.id
            if key not in self.subscriptions:
                self.subscriptions[key] = async_track_state_change_event(
                    self.hass, [state.entity_id], self.source_changed
                )
            source.refresh()
        # Retain existing entities for unavailable/removed inputs; do not duplicate
        # them or count them in the summaries. Reappearing sources reuse the key.
        for key, source in self.sources.items():
            if key not in found:
                source.refresh()
        self.refresh_aggregates()

    @callback
    def source_changed(self, event):
        if self.stopped:
            return
        entity_id = event.data["entity_id"]
        for source in self.sources.values():
            if source.source_id == entity_id:
                source.refresh()
        self.refresh_aggregates()

    @callback
    def refresh_aggregates(self):
        for entity in self.aggregates:
            entity.refresh()

    def current_values(self):
        return [self.source_value(source) for source in self.sources.values()]


class BaseAQI(SensorEntity):
    _attr_should_poll = False
    _attr_device_class = SensorDeviceClass.AQI
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:air-filter"
    _attr_native_value = None
    _attr_available = False
    _ready = False

    @callback
    def refresh(self):
        value, attrs = self.read()
        attrs["method"] = METHOD
        attrs["category"] = category(value)
        changed = (self._attr_native_value != value
                   or self._attr_available != (value is not None)
                   or getattr(self, "_attr_extra_state_attributes", None) != attrs)
        self._attr_native_value = value
        self._attr_available = value is not None
        self._attr_extra_state_attributes = attrs
        if self._ready and changed:
            self.async_write_ha_state()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self._ready = True
        self.refresh()

    async def async_will_remove_from_hass(self):
        self._ready = False
        await super().async_will_remove_from_hass()


class RoomAQI(BaseAQI):
    def __init__(self, manager, key, source_id, name, registry_id):
        self.manager = manager
        self.source_id = source_id
        self.registry_id = registry_id
        self._attr_unique_id = f"source_{key}"
        self._attr_name = name
        self.refresh()

    def read(self):
        state = self.manager.hass.states.get(self.source_id)
        value = self.manager.source_value(self)
        return value, {
            "source_entity_id": self.source_id,
            "pm25": state.state if value is not None and state else None,
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        # Assign area on initial creation, without moving a user-assigned area.
        entry = self.manager.registry.async_get(self.entity_id)
        area_id = self.manager.area_for(self.source_id)
        if entry and entry.area_id is None and area_id:
            self.manager.registry.async_update_entity(self.entity_id, area_id=area_id)


class SummaryAQI(BaseAQI):
    def __init__(self, manager, kind):
        self.manager = manager
        self.kind = kind
        self._attr_unique_id = f"indoor_{kind}"
        self._attr_name = "실내 평균 AQI" if kind == "average" else "실내 최고 AQI"
        self._attr_icon = "mdi:home-analytics" if kind == "average" else "mdi:alert-circle-outline"
        self.refresh()

    def read(self):
        values = self.manager.current_values()
        average, maximum = summarize(values)
        return (average if self.kind == "average" else maximum), {
            "valid_sources": sum(value is not None for value in values),
            "total_sources": len(values),
        }
