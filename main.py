import os
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

ROOT = Path(__file__).parent
DB = ROOT / "data.db"
app = FastAPI(title="Android GPT")
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", secrets.token_hex(32)), same_site="lax", https_only=False)

HTML = '''<!doctype html><html lang="pt"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Android GPT</title><style>
*{box-sizing:border-box}body{margin:0;background:#090b10;color:#eef1f6;font:15px system-ui,-apple-system,sans-serif}a{color:inherit;text-decoration:none}.shell{display:flex;min-height:100vh}.side{width:230px;background:#0e1118;border-right:1px solid #202532;padding:22px 14px;position:fixed;inset:0 auto 0 0}.brand{font-weight:800;font-size:20px;padding:0 10px 24px}.nav a{display:block;padding:11px 12px;border-radius:9px;color:#aab2c0;margin:3px 0}.nav a:hover,.nav .active{background:#191e28;color:#fff}.main{margin-left:230px;width:calc(100% - 230px);padding:30px;max-width:1500px}.top{display:flex;justify-content:space-between;align-items:center;margin-bottom:26px}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.card{background:#11151d;border:1px solid #202633;border-radius:14px;padding:18px}.muted{color:#8e98a8}.big{font-size:30px;font-weight:800;margin-top:8px}.devices{margin-top:18px}.device{display:flex;align-items:center;justify-content:space-between;border:1px solid #202633;background:#11151d;padding:15px;border-radius:12px;margin:9px 0}.dot{display:inline-block;width:9px;height:9px;border-radius:50%;background:#687080;margin-right:8px}.on{background:#4ade80}.btn{border:0;background:#fff;color:#080a0e;padding:10px 14px;border-radius:9px;font-weight:700;cursor:pointer}.btn.secondary{background:#202633;color:#fff}.btn.danger{background:#5b2027;color:#fff}.actions{display:flex;gap:8px;flex-wrap:wrap}.form{max-width:720px}.input,select{width:100%;background:#0b0e14;color:#fff;border:1px solid #2a3040;border-radius:9px;padding:12px;margin:7px 0 15px}.check{display:flex;gap:10px;margin:10px 0}.login{min-height:100vh;display:grid;place-items:center}.login .card{width:min(420px,92vw)}h1{margin:0 0 7px}h2{margin-top:0}.note{padding:12px;border-radius:9px;background:#161b24;color:#aeb7c5;margin:15px 0}.cmd{display:grid;grid-template-columns:1fr 1fr;gap:10px}.mono{font-family:ui-monospace,monospace;background:#080a0f;padding:12px;border-radius:8px;white-space:pre-wrap}
@media(max-width:800px){.side{width:68px}.brand{font-size:0}.brand:after{content:'AG';font-size:18px}.nav a{font-size:0}.nav a:before{content:'•';font-size:20px}.main{margin-left:68px;width:calc(100% - 68px);padding:18px}.grid{grid-template-columns:1fr 1fr}.cmd{grid-template-columns:1fr}}
</style></head><body>{body}</body></html>'''

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
    c.execute('CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE,password TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS devices(id TEXT PRIMARY KEY,name TEXT,model TEXT,android TEXT,last_seen REAL,online INTEGER DEFAULT 0,token TEXT UNIQUE)')
    c.commit(); return c

def page(body): return HTML.format(body=body)
def nav(active='dashboard'):
    return f'''<aside class="side"><div class="brand">Android GPT</div><nav class="nav">
    <a class="{'active' if active=='dashboard' else ''}" href="/">Geral</a>
    <a class="{'active' if active=='generator' else ''}" href="/generator">Gerador</a>
    <a class="{'active' if active=='devices' else ''}" href="/devices">Telemóveis</a>
    <a href="/logout">Sair</a></nav></aside>'''

def authed(request): return request.session.get('user')

@app.on_event('startup')
def startup():
    c=db();
    if not c.execute('SELECT 1 FROM users LIMIT 1').fetchone():
        c.execute('INSERT INTO users(username,password) VALUES(?,?)',('admin',os.getenv('ADMIN_PASSWORD','change-me'))); c.commit()
    c.close()

@app.get('/login',response_class=HTMLResponse)
def login():
    return page('''<div class="login"><div class="card"><h1>Android GPT</h1><p class="muted">Painel de gestão Android</p><form method="post"><label>Utilizador</label><input class="input" name="username" value="admin"><label>Password</label><input class="input" type="password" name="password"><button class="btn">Entrar</button></form></div></div>''')

@app.post('/login')
def login_post(request:Request,username:str=Form(...),password:str=Form(...)):
    c=db(); u=c.execute('SELECT * FROM users WHERE username=? AND password=?',(username,password)).fetchone(); c.close()
    if not u: return RedirectResponse('/login?error=1',303)
    request.session['user']=username; return RedirectResponse('/',303)

@app.get('/logout')
def logout(request:Request): request.session.clear(); return RedirectResponse('/login',303)

@app.get('/',response_class=HTMLResponse)
def dashboard(request:Request):
    if not authed(request): return RedirectResponse('/login',303)
    c=db(); total=c.execute('SELECT COUNT(*) n FROM devices').fetchone()['n']; online=c.execute('SELECT COUNT(*) n FROM devices WHERE online=1').fetchone()['n'];
    recent=c.execute('SELECT * FROM devices ORDER BY last_seen DESC LIMIT 8').fetchall(); c.close()
    rows=''.join(f'<div class="device"><div><b>{d["name"]}</b><div class="muted">{d["model"] or "Android"} · Android {d["android"] or "?"}</div></div><div><span class="dot {"on" if d["online"] else ""}"></span>{"Online" if d["online"] else "Offline"} <a class="btn secondary" href="/devices/{d["id"]}">Abrir</a></div></div>' for d in recent)
    body=nav()+f'''<main class="main"><div class="top"><div><h1>Geral</h1><div class="muted">Visão geral dos teus dispositivos autorizados.</div></div></div><div class="grid"><div class="card"><div class="muted">Telemóveis ligados</div><div class="big">{total}</div></div><div class="card"><div class="muted">Online agora</div><div class="big">{online}</div></div><div class="card"><div class="muted">Offline</div><div class="big">{total-online}</div></div><div class="card"><div class="muted">Estado</div><div class="big">OK</div></div></div><section class="devices"><h2>Últimos dispositivos</h2>{rows or '<div class="card muted">Ainda não existem dispositivos emparelhados.</div>'}</section></main>'''
    return page(body)

@app.get('/generator',response_class=HTMLResponse)
def generator(request:Request):
    if not authed(request): return RedirectResponse('/login',303)
    body=nav('generator')+'''<main class="main"><h1>Gerador Android</h1><p class="muted">Cria uma configuração de agente para os teus próprios dispositivos.</p><div class="card form"><form method="post" action="/generator"><label>Nome da app</label><input class="input" name="app_name" value="Android GPT Agent"><label>URL do servidor</label><input class="input" name="server_url" placeholder="https://teu-servidor.example"><div class="check"><input type="checkbox" name="battery" checked> Estado da bateria</div><div class="check"><input type="checkbox" name="device" checked> Informações do dispositivo</div><div class="check"><input type="checkbox" name="notifications"> Notificações</div><div class="check"><input type="checkbox" name="files"> Ficheiros escolhidos pelo utilizador</div><div class="note">O APK deve pedir permissões Android normalmente e só liga depois do emparelhamento.</div><button class="btn">Gerar projeto Android</button></form></div></main>'''
    return page(body)

@app.post('/generator')
def generator_post(request:Request,app_name:str=Form(...),server_url:str=Form(...),battery:Optional[str]=Form(None),device:Optional[str]=Form(None),notifications:Optional[str]=Form(None),files:Optional[str]=Form(None)):
    if not authed(request): return RedirectResponse('/login',303)
    cfg={'app_name':app_name,'server_url':server_url,'features':{'battery':bool(battery),'device':bool(device),'notifications':bool(notifications),'files':bool(files)}}
    return JSONResponse({'status':'generated','project_config':cfg,'next':'build the Android project with Gradle/Android Studio'})

@app.get('/devices',response_class=HTMLResponse)
def devices(request:Request):
    if not authed(request): return RedirectResponse('/login',303)
    c=db(); ds=c.execute('SELECT * FROM devices ORDER BY online DESC,last_seen DESC').fetchall(); c.close()
    rows=''.join(f'<div class="device"><div><b>{d["name"]}</b><div class="muted">{d["id"]} · {d["model"] or "Android"}</div></div><div><span class="dot {"on" if d["online"] else ""}"></span><a class="btn secondary" href="/devices/{d["id"]}">Controlar</a></div></div>' for d in ds)
    return page(nav('devices')+f'<main class="main"><h1>Telemóveis</h1><p class="muted">Apenas dispositivos emparelhados e autorizados.</p>{rows or "<div class=card>Nenhum dispositivo.</div>"}</main>')

@app.get('/devices/{device_id}',response_class=HTMLResponse)
def device(request:Request,device_id:str):
    if not authed(request): return RedirectResponse('/login',303)
    c=db(); d=c.execute('SELECT * FROM devices WHERE id=?',(device_id,)).fetchone(); c.close()
    if not d: return HTMLResponse(page(nav('devices')+'<main class="main"><h1>Dispositivo não encontrado</h1></main>'),404)
    body=nav('devices')+f'''<main class="main"><h1>{d["name"]}</h1><div class="grid"><div class="card"><div class="muted">Estado</div><div class="big">{"Online" if d["online"] else "Offline"}</div></div><div class="card"><div class="muted">Modelo</div><div class="big">{d["model"] or "—"}</div></div><div class="card"><div class="muted">Android</div><div class="big">{d["android"] or "—"}</div></div><div class="card"><div class="muted">ID</div><div class="mono">{d["id"]}</div></div></div><div class="card" style="margin-top:18px"><h2>Comandos autorizados</h2><div class="actions"><button class="btn" onclick="cmd('ping')">Ping</button><button class="btn secondary" onclick="cmd('notify')">Enviar notificação</button><button class="btn secondary" onclick="cmd('refresh')">Atualizar estado</button></div><div id="out" class="mono" style="margin-top:14px">Aguardando comando…</div></div><script>async function cmd(c){{let r=await fetch('/api/devices/{d["id"]}/command',{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify({{command:c}})}});document.querySelector('#out').textContent=await r.text()}}</script></main>'''
    return page(body)

connections={}

@app.websocket('/ws/{token}')
async def ws(websocket:WebSocket,token:str):
    c=db(); d=c.execute('SELECT * FROM devices WHERE token=?',(token,)).fetchone();
    if not d: await websocket.close(code=1008); c.close(); return
    await websocket.accept(); connections[d['id']]=websocket; c.execute('UPDATE devices SET online=1,last_seen=? WHERE id=?',(time.time(),d['id'])); c.commit(); c.close()
    try:
        while True:
            msg=await websocket.receive_json();
            c=db(); c.execute('UPDATE devices SET last_seen=?,online=1 WHERE id=?',(time.time(),d['id'])); c.commit(); c.close()
    except WebSocketDisconnect:
        connections.pop(d['id'],None); c=db(); c.execute('UPDATE devices SET online=0,last_seen=? WHERE id=?',(time.time(),d['id'])); c.commit(); c.close()

@app.post('/api/register')
async def register(request:Request):
    data=await request.json(); device_id=data.get('id') or secrets.token_hex(8); token=secrets.token_urlsafe(32)
    c=db(); c.execute('INSERT INTO devices(id,name,model,android,last_seen,online,token) VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,model=excluded.model,android=excluded.android,token=excluded.token',(device_id,data.get('name','Android'),data.get('model',''),data.get('android',''),time.time(),0,token)); c.commit(); c.close(); return {'device_id':device_id,'token':token,'websocket':'/ws/'+token}

@app.post('/api/devices/{device_id}/command')
async def command(request:Request,device_id:str):
    if not authed(request): return JSONResponse({'error':'login required'},401)
    data=await request.json(); allowed={'ping','notify','refresh'}; command=data.get('command')
    if command not in allowed: return JSONResponse({'error':'command not allowed'},400)
    ws=connections.get(device_id)
    if not ws: return JSONResponse({'error':'device offline'},409)
    await ws.send_json({'type':'command','command':command}); return {'sent':True,'command':command}

@app.get('/health')
def health(): return {'ok':True}

if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='0.0.0.0',port=int(os.getenv('PORT','80')))
