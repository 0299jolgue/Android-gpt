from ..database import get_device, list_devices, set_device_status, upsert_device

def register_device(device_id: str, name: str, model: str, android_version: str):
    return upsert_device(device_id, name, model, android_version)

def get_devices():
    return list_devices()

def get_device_by_id(device_id: str):
    return get_device(device_id)

def mark_online(device_id: str):
    set_device_status(device_id, "online")
