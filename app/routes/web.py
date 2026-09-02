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


def render(request: Request, name: str, context: dict, status_code: int = 200):
    context = dict(context)
    context["request"] = request
    return templates.TemplateResponse(request=request, name=name, context=context, status_code=status_code)


@router.get("/health", response_class=HTMLResponse)
def health():
    # Return a plain 200 for platform/reverse-proxy health checks.
    return HTMLResponse("OK", status_code=200)


@router.get("/login", response_class=HTMLResponse)
def login(request: Request):
    return render(request, "login.html", {"error": None})


@router.post("/login")
def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    user = get_user(username)
    if not user or not verify_password(password, user["password_hash"]):
        return render(request, "login.html", {"error": "Credenciais inválidas."}, 401)
    request.session["user"] = username
    return RedirectResponse("/", status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    # Keep the public entry route at HTTP 200 so platform proxies and health
    # monitors can reach the app; unauthenticated users simply see login.
    if not is_authenticated(request):
        return render(request, "login.html", {"error": None})
    devices = list_devices()
    online = sum(d["status"] == "online" for d in devices)
    return render(request, "dashboard.html", {"devices": devices, "total": len(devices), "online": online, "offline": len(devices)-online, "active": "dashboard"})


@router.get("/devices", response_class=HTMLResponse)
def devices_page(request: Request):
    if (r := guard(request)): return r
    return render(request, "devices.html", {"devices": list_devices(), "active": "devices"})


@router.get("/devices/{device_id}", response_class=HTMLResponse)
def device_page(request: Request, device_id: str):
    if (r := guard(request)): return r
    device = get_device(device_id)
    if not device:
        return render(request, "device.html", {"device": None, "active": "devices"}, 404)
    return render(request, "device.html", {"device": device, "active": "devices"})


@router.get("/generator", response_class=HTMLResponse)
def generator_page(request: Request):
    if (r := guard(request)): return r
    return render(request, "generator.html", {"active": "generator", "result": None})
