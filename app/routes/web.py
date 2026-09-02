from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from ..config import settings
from ..database import get_user, list_devices, get_device
from ..security import verify_password, is_authenticated

templates = Jinja2Templates(directory=str(settings.templates))
router = APIRouter()

def guard(request: Request):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=303)
    return None

@router.get("/login", response_class=HTMLResponse)
def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})

@router.post("/login")
def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    user = get_user(username)
    if not user or not verify_password(password, user["password_hash"]):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Credenciais inválidas."}, status_code=401)
    request.session["user"] = username
    return RedirectResponse("/", status_code=303)

@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)

@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    if (r := guard(request)): return r
    devices = list_devices()
    online = sum(d["status"] == "online" for d in devices)
    return templates.TemplateResponse("dashboard.html", {"request": request, "devices": devices, "total": len(devices), "online": online, "offline": len(devices)-online, "active": "dashboard"})

@router.get("/devices", response_class=HTMLResponse)
def devices_page(request: Request):
    if (r := guard(request)): return r
    return templates.TemplateResponse("devices.html", {"request": request, "devices": list_devices(), "active": "devices"})

@router.get("/devices/{device_id}", response_class=HTMLResponse)
def device_page(request: Request, device_id: str):
    if (r := guard(request)): return r
    device = get_device(device_id)
    if not device:
        return templates.TemplateResponse("device.html", {"request": request, "device": None, "active": "devices"}, status_code=404)
    return templates.TemplateResponse("device.html", {"request": request, "device": device, "active": "devices"})

@router.get("/generator", response_class=HTMLResponse)
def generator_page(request: Request):
    if (r := guard(request)): return r
    return templates.TemplateResponse("generator.html", {"request": request, "active": "generator", "result": None})
