# Telegram vacancy bot (webhook + SQLite)

Минимальный Telegram-бот на Flask, который:
- использует **webhook**;
- показывает **кнопки** (inline keyboard);
- хранит пользователей в **SQLite** (`bot.db`).

## Быстрый старт

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Создайте `.env` или экспортируйте переменные:

```bash
export BOT_TOKEN="<telegram_bot_token>"
export WEBHOOK_URL="https://your-domain.com"
export WEBHOOK_SECRET="optional_secret"
export PORT=8080
```

Запуск:

```bash
python app.py
```

## Настройка webhook

После запуска приложения вызовите:

```bash
curl -X POST http://localhost:8080/set-webhook
```

Webhook будет установлен в `https://your-domain.com/webhook`.

## Доступные эндпоинты

- `POST /webhook` — принимает обновления от Telegram.
- `POST /set-webhook` — регистрирует webhook в Telegram API.
- `GET /health` — проверка статуса.

## Поведение бота

- `/start` — приветствие + кнопки.
- Кнопка `👤 Профиль` — показывает данные пользователя из SQLite.
- Кнопка `ℹ️ Помощь` — показывает справку.

Пользователь сохраняется/обновляется в таблице `users` при каждом сообщении или callback.
