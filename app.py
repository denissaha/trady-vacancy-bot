import logging
import os
import sqlite3
from contextlib import closing
from datetime import datetime

import requests
from flask import Flask, abort, jsonify, request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
DB_PATH = os.getenv("DB_PATH", "bot.db")

app = Flask(__name__)


def init_db() -> None:
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


init_db()


def upsert_user(user: dict) -> None:
    now = datetime.utcnow().isoformat()
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute(
            """
            INSERT INTO users (id, username, first_name, last_name, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id)
            DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                updated_at = excluded.updated_at
            """,
            (
                user.get("id"),
                user.get("username"),
                user.get("first_name"),
                user.get("last_name"),
                now,
                now,
            ),
        )
        conn.commit()


def get_user(user_id: int) -> tuple | None:
    with closing(sqlite3.connect(DB_PATH)) as conn:
        row = conn.execute(
            "SELECT id, username, first_name, last_name, created_at, updated_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return row


def telegram_api(method: str, payload: dict) -> None:
    if not BOT_TOKEN:
        logger.warning("BOT_TOKEN is not configured, skipping send")
        return

    response = requests.post(f"{BASE_URL}/{method}", json=payload, timeout=10)
    if response.status_code != 200:
        logger.error("Telegram API error %s: %s", response.status_code, response.text)


def send_text(chat_id: int, text: str) -> None:
    inline = {
        "inline_keyboard": [
            [{"text": "👤 Профиль", "callback_data": "profile"}],
            [{"text": "ℹ️ Помощь", "callback_data": "help"}],
        ]
    }
    telegram_api(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
            "reply_markup": inline,
        },
    )


def send_profile(chat_id: int, user_id: int) -> None:
    user = get_user(user_id)
    if not user:
        send_text(chat_id, "Пользователь не найден в базе. Нажмите /start")
        return
    uid, username, first_name, last_name, created_at, updated_at = user
    text = (
        "Ваш профиль:\n"
        f"ID: {uid}\n"
        f"Username: @{username if username else 'не указан'}\n"
        f"Имя: {first_name or '-'} {last_name or ''}\n"
        f"Создан: {created_at}\n"
        f"Обновлен: {updated_at}"
    )
    send_text(chat_id, text)


@app.post("/webhook")
def webhook() -> tuple[dict, int]:
    if WEBHOOK_SECRET:
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if secret != WEBHOOK_SECRET:
            abort(403)

    update = request.get_json(silent=True) or {}

    message = update.get("message")
    callback_query = update.get("callback_query")

    if message:
        user = message.get("from", {})
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "")

        if user:
            upsert_user(user)

        if chat_id:
            if text == "/start":
                send_text(chat_id, "Привет! Это бот с webhook и SQLite. Выберите действие:")
            elif text in {"👤 Профиль", "/profile"}:
                send_profile(chat_id, user.get("id"))
            elif text in {"ℹ️ Помощь", "/help"}:
                send_text(chat_id, "Доступные команды: /start, /profile, /help")
            else:
                send_text(chat_id, "Не понял команду. Нажмите кнопку или /help")

    if callback_query:
        cq_id = callback_query.get("id")
        data = callback_query.get("data")
        from_user = callback_query.get("from", {})
        chat_id = callback_query.get("message", {}).get("chat", {}).get("id")

        if from_user:
            upsert_user(from_user)

        if chat_id and data == "profile":
            send_profile(chat_id, from_user.get("id"))
        elif chat_id and data == "help":
            send_text(chat_id, "Используйте кнопки или команды /start /profile /help")

        if cq_id:
            telegram_api("answerCallbackQuery", {"callback_query_id": cq_id})

    return jsonify({"ok": True}), 200


@app.post("/set-webhook")
def set_webhook() -> tuple[dict, int]:
    public_url = os.getenv("WEBHOOK_URL", "")
    if not public_url:
        return jsonify({"ok": False, "error": "WEBHOOK_URL is not set"}), 400

    payload = {"url": f"{public_url}/webhook"}
    if WEBHOOK_SECRET:
        payload["secret_token"] = WEBHOOK_SECRET

    response = requests.post(f"{BASE_URL}/setWebhook", json=payload, timeout=10)
    return jsonify(response.json()), response.status_code


@app.get("/health")
def health() -> tuple[dict, int]:
    return {"status": "ok"}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
