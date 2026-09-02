import time
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from ..database import upsert_device, get_device, list_devices, set_device_status
from ..security import is_authenticated
from ..services.generator import create_project

router = APIRouter()

@router.get("/health")
def health():
    return {"ok": True, "service": "android-gpt"}

@router.get("/stats")
def stats():
    devices = list_devices()
    online = sum(d["status"] == "online" for d in devices)
    return {"total": len(devices), "online": online, "offline": len(devices) - online}

@router.post("/generator")
async def generator(request: Request):
    if not is_authenticated(request):
        return JSONResponse({"ok": False, "error": "login_required"}, status_code=401)
    data = await request.form()
    project = create_project(str(data.get("app_name", "Android GPT Agent")), str(data.get("server_url", "")), {
        "device_info": bool(data.get("device_info")),
        "battery": bool(data.get("battery")),
        "notifications": bool(data.get("notifications")),
        "selected_files": bool(data.get("selected_files")),
    })
    return {"ok": True, "project": str(project.relative_to(project.parents[1]))}

@router.post("/devices/register")
async def register(request: Request):
    data = await request.json()
    device_id = str(data.get("id", "")).strip()
    if not device_id:
        return {"ok": False, "error": "id is required"}
    token = upsert_device(device_id, str(data.get("name", "Android device")), str(data.get("model", "")), str(data.get("android_version", "")))
    return {"ok": True, "device_id": device_id, "token": token}

@router.get("/devices/{device_id}")
def device_info(device_id: str):
    device = get_device(device_id)
    if not device:
        return JSONResponse({"ok": False, "error": "not_found"}, status_code=404)
    return {"ok": True, "device": dict(device)}

@router.post("/devices/{device_id}/heartbeat")
def heartbeat(device_id: str):
    if not get_device(device_id):
        return JSONResponse({"ok": False, "error": "not_found"}, status_code=404)
    set_device_status(device_id, "online")
    return {"ok": True, "timestamp": time.time()}

@router.get("/devices")
def devices():
    return {"devices": [dict(d) for d in list_devices()]}

@router.get("/admin/status")
def admin_status(request: Request):
    if not is_authenticated(request):
        return JSONResponse({"ok": False, "error": "login_required"}, status_code=401)
    return stats()
