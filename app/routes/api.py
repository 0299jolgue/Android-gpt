import json
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse

from ..config import settings
from ..database import get_device, list_devices, set_device_status, upsert_device
from ..security import is_authenticated
from ..services.apk_builder import build_apk
from ..services.generator import FEATURES, create_project

router = APIRouter()
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="apk-builder")
_jobs: dict[str, dict] = {}


def _public_server_url(request: Request) -> str:
    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
    scheme = forwarded_proto or request.url.scheme
    host = request.headers.get("x-forwarded-host", "").split(",")[0].strip() or request.headers.get("host", "").strip()
    if not host:
        host = request.url.netloc
    return f"{scheme}://{host}".rstrip("/")


def _safe_slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return (value.strip("._-") or "android_gpt_agent")[:48]


def _cache_paths(app_name: str) -> tuple[Path, Path]:
    base = _safe_slug(app_name)
    apk = settings.generated / "apks" / f"{base}.apk"
    metadata = settings.generated / "apks" / f"{base}.json"
    return apk, metadata


def _cached_apk(app_name: str, server_url: str, features: dict[str, bool]) -> Path | None:
    apk, metadata = _cache_paths(app_name)
    if not apk.is_file() or not metadata.is_file():
        return None
    try:
        saved = json.loads(metadata.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    wanted = {
        "app_name": app_name,
        "server_url": server_url.rstrip("/"),
        "features": features,
    }
    return apk if saved == wanted else None


def _save_cache_metadata(app_name: str, server_url: str, features: dict[str, bool]) -> None:
    _, metadata = _cache_paths(app_name)
    metadata.parent.mkdir(parents=True, exist_ok=True)
    metadata.write_text(
        json.dumps(
            {"app_name": app_name, "server_url": server_url.rstrip("/"), "features": features},
            indent=2,
        ),
        encoding="utf-8",
    )


def _run_build(job_id: str, app_name: str, server_url: str, features: dict[str, bool]) -> None:
    _jobs[job_id].update({"status": "building", "message": "A preparar o ambiente Android e a compilar o APK…"})
    try:
        apk = _cached_apk(app_name, server_url, features)
        if apk is not None:
            _jobs[job_id].update({
                "status": "ready",
                "message": "APK já existente para esta configuração — pronto imediatamente.",
                "download": f"/api/generator/download/{apk.name}",
            })
            return

        apk, project = build_apk(app_name, server_url, features)
        _save_cache_metadata(app_name, server_url, features)
        _jobs[job_id].update({
            "status": "ready",
            "message": "APK pronto.",
            "download": f"/api/generator/download/{apk.name}",
            "project": str(project.relative_to(settings.generated)),
        })
    except Exception as exc:
        _jobs[job_id].update({"status": "error", "message": str(exc)})


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
    app_name = str(data.get("app_name", "Android GPT Agent")).strip() or "Android GPT Agent"
    server_url = _public_server_url(request)
    features = {name: bool(data.get(name)) for name in FEATURES}
    create_project(app_name, server_url, features)

    job_id = uuid.uuid4().hex
    cached = _cached_apk(app_name, server_url, features)
    if cached is not None:
        _jobs[job_id] = {
            "status": "ready",
            "message": "APK já existente para esta configuração — pronto imediatamente.",
            "app_name": app_name,
            "download": f"/api/generator/download/{cached.name}",
        }
        return {"ok": True, "job_id": job_id, "status_url": f"/api/generator/status/{job_id}"}

    _jobs[job_id] = {
        "status": "queued",
        "message": "APK colocado na fila de compilação. Podes mudar de aba ou fechar o navegador.",
        "app_name": app_name,
    }
    _executor.submit(_run_build, job_id, app_name, server_url, features)
    return {"ok": True, "job_id": job_id, "status_url": f"/api/generator/status/{job_id}"}


@router.get("/generator/status/{job_id}")
def generator_status(request: Request, job_id: str):
    if not is_authenticated(request):
        return JSONResponse({"ok": False, "error": "login_required"}, status_code=401)
    job = _jobs.get(job_id)
    if not job:
        return JSONResponse({"ok": False, "error": "job_not_found"}, status_code=404)
    return {"ok": True, "job_id": job_id, **job}


@router.get("/generator/download/{filename}")
def generator_download(request: Request, filename: str):
    if not is_authenticated(request):
        return JSONResponse({"ok": False, "error": "login_required"}, status_code=401)
    safe = Path(filename).name
    path = settings.generated / "apks" / safe
    if path.parent != settings.generated / "apks" or not path.is_file() or path.suffix.lower() != ".apk":
        return JSONResponse({"ok": False, "error": "apk_not_found"}, status_code=404)
    return FileResponse(path, media_type="application/vnd.android.package-archive", filename=safe)


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
