# Android GPT

Painel web modular para gerir dispositivos Android autorizados e preparar projetos Android.

## Arranque

O único entrypoint é:

```bash
python starter.py
```

O servidor usa a porta `80` por defeito (`PORT` pode substituir).

## Estrutura

```text
.
├── starter.py
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── factory.py
│   ├── config.py
│   ├── database.py
│   ├── security.py
│   ├── state.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── web.py
│   │   └── api.py
│   └── services/
│       ├── __init__.py
│       ├── device_service.py
│       └── generator.py
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── devices.html
│   ├── device.html
│   └── generator.html
├── static/
│   ├── css/app.css
│   └── js/app.js
├── data/
└── generated/
```

## Painel

- Login privado
- Geral: total, online, offline
- Lista de telemóveis
- Página individual por dispositivo
- Registo e heartbeat de dispositivos
- Gerador de configurações/projetos Android
- Templates HTML separados de CSS/JS

As operações Android devem ser visíveis ao utilizador do dispositivo e limitadas às funções selecionadas para a aplicação.
