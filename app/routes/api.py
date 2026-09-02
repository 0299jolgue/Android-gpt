import time
from fastapi import APIRouter, Request
from ..database import upsert_device, get_device, list_devices
from ..security import is_authenticated

router = APIRouter()

@router.get("/health")
def health():
    return {"ok": True, "service": "android-gpt"}

@router.get("/stats")
def stats():
    devices = list_devices()
    online = sum(d["status"] == "online" for d in devices)
    return {"total": len(devices), "online": online, "offline": len(devices) - online}

@router.post("/devices/register")
async def register(request: Request):
    data = await request.json()
    device_id = str(data.get("id", "")).strip()
    if not device_id:
        return {"ok": False, "error": "id is required"}
    token = upsert_device(
        device_id,
        str(data.get("name", "Android device")),
        str(data.get("model", "")),
        str(data.get("android_version", "")),
    )
    return {"ok": True, "device_id": device_id, "token": token}

@router.get("/devices/{device_id}")
def device_info(device_id: str):
    device = get_device(device_id)
    if not device:
        return {"ok": False, "error": "not_found"}
    return {"ok": True, "device": dict(device)}

@router.post("/devices/{device_id}/heartbeat")
def heartbeat(device_id: str):
    from ..database import set_device_status
    if not get_device(device_id):
        return {"ok": False, "error": "not_found"}
    set_device_status(device_id, "online")
    return {"ok": True, "timestamp": time.time()}

@router.get("/devices")
def devices():
    return {"devices": [dict(d) for d in list_devices()]}

@router.get("/admin/status")
def admin_status(request: Request):
    if not is_authenticated(request):
        return {"ok": False, "error": "login_required"}
    return stats()
