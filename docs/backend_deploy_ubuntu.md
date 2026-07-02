# Backend на Ubuntu VPS

Сервер пользователя:

- Ubuntu 22.04
- 1 CPU, 1 GB RAM
- IPv4: `72.56.82.120`
- вход: `ssh root@72.56.82.120`
- домена пока нет

## 1. Установка системных пакетов

```bash
apt update
apt install -y git python3 python3-venv python3-pip nginx
```

## 2. Загрузка проекта

```bash
cd /opt
git clone <URL_GITHUB_REPO> forklift-logistics
cd /opt/forklift-logistics
```

## 3. Python-окружение

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Проверка API

```bash
./run_api.sh
```

В другом терминале:

```bash
curl http://72.56.82.120:8000/health
curl http://72.56.82.120:8000/scenarios
```

Документация FastAPI:

```text
http://72.56.82.120:8000/docs
```

## 5. Systemd-сервис

Создать файл:

```bash
nano /etc/systemd/system/forklift-api.service
```

Содержимое:

```ini
[Unit]
Description=Forklift Logistics FastAPI backend
After=network.target

[Service]
WorkingDirectory=/opt/forklift-logistics
ExecStart=/opt/forklift-logistics/.venv/bin/python -m uvicorn app.api:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Запуск:

```bash
systemctl daemon-reload
systemctl enable forklift-api
systemctl start forklift-api
systemctl status forklift-api
```

## 6. Nginx reverse proxy

Создать файл:

```bash
nano /etc/nginx/sites-available/forklift-api
```

Содержимое:

```nginx
server {
    listen 80;
    server_name 72.56.82.120;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Активировать:

```bash
ln -s /etc/nginx/sites-available/forklift-api /etc/nginx/sites-enabled/forklift-api
nginx -t
systemctl reload nginx
```

После этого API будет доступно:

```text
http://72.56.82.120/health
http://72.56.82.120/docs
```

## 7. HTTPS

Для нормального HTTPS нужен домен или поддомен, который указывает на IP `72.56.82.120`.

После появления домена:

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d api.example.ru
```

Без домена можно временно использовать HTTP по IP для теста backend. Для iOS лучше перейти на домен + HTTPS перед финальной демонстрацией.
