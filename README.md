# Ping Hosts App

Приложение для пинга IP-адресов с фронтом на React и бэком на FastAPI + SQLite.

---

## 📦 Структура проекта

```
ping_hosts_drillservices_test/
├── backend/                # FastAPI + SQLite
│   ├── Dockerfile
│   ├── main.py
│   ├── hosts.db
│   └── requirements.txt
├── frontend/               # React (TypeScript)
│   ├── src/
│   ├── public/
│   ├── Dockerfile
│   └── ...
├── docker-compose.yml      # Общий docker-compose
├── sample_ips.csv
```

---

## 🚀 Быстрый старт

### 1. Собрать и запустить

```bash
docker compose up --build
```

- Бэкенд будет доступен на: http://localhost:8000
- Фронтэнд — на: http://localhost:3000

---

## ⚙️ API

- `GET /hosts` — список хостов
- `POST /hosts` — добавить хост
- `PUT /hosts/{id}` — редактировать хост
- `DELETE /hosts/{id}` — удалить хост
- `POST /hosts/import` — импорт из CSV
- `GET /stats/export` — экспорт в CSV

---

## 🧪 Примеры IP для пинга

```
8.8.8.8
1.1.1.1
77.88.8.8
208.67.222.222
```

---

## 💾 База данных

Используется SQLite (`hosts.db`) внутри контейнера.

---

## 🛠 Зависимости (backend)

```txt
fastapi
uvicorn[standard]
sqlalchemy
pydantic
ping3
python-multipart
```