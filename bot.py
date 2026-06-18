import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id
import requests
import csv
import re
import json
import os
from io import StringIO

# ==================== НАСТРОЙКИ ====================
VK_TOKEN = "vk1.a.tJGT6GPZybsXLJJSqQOYpyLGYIpL-0EJQPQN3IvOffvyGJ7bTxpkkp5LX1YhJQXpYFeZLJVVvv8cpxYU-HZyHpewUcGzx8-xOWZWs-YAmvecVRau_m4M8EhtH2bw2IPvvMmAEODWz7SJQK98Qi516sOv1h-fgbqtOqz-Sv_e63eMQNW_7OaMExGQZZgkHOBU9xWSt-Umv6Cewhq-UJFCQQ"
TABLE_URL = "https://docs.google.com/spreadsheets/d/1zgg1T2lNCJS4IJuk_AjV3Qvw9WW4Gf3XdLyamscVoOY/edit?usp=drivesdk"
SHEET_NAME = "Лист1"
CHAT_ID = 1  # ID беседы

# Столбцы
COL_NICKNAME = 0    # A
COL_POSITION = 1    # B
COL_EXTRA = 2       # C
COL_WARNINGS = 10   # K
COL_REPRIMANDS = 11 # L
COL_REPUTATION = 49 # AX
COL_INACTIVES = 50  # AY
COL_DAYS = 51       # AZ
# ===================================================

match = re.search(r'/d/([a-zA-Z0-9-_]+)', TABLE_URL)
TABLE_ID = match.group(1)

vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()
longpoll = VkLongPoll(vk_session)

# Защита от дублей — храним обработанные message_id
PROCESSED_MESSAGES = set()

def load_json(filename):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_sheet_data():
    url = f"https://docs.google.com/spreadsheets/d/{TABLE_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_NAME}"
    r = requests.get(url)
    r.encoding = 'utf-8'
    return list(csv.reader(StringIO(r.text)))

def get_val(row, index):
    if index < len(row) and row[index].strip():
        return row[index].strip()
    return "—"

def find_admin(data, nickname):
    if not data or len(data) < 2:
        return None
    for row in data[1:]:
        if len(row) > COL_NICKNAME and row[COL_NICKNAME].strip().lower() == nickname.lower():
            return row
    return None

def format_stats(row):
    return f"""📊 Статистика администратора:

Никнейм администратора: {get_val(row, COL_NICKNAME)}
Должность: {get_val(row, COL_POSITION)}
Доп. должность: {get_val(row, COL_EXTRA)}
Предупреждений: {get_val(row, COL_WARNINGS)}
Выговоров: {get_val(row, COL_REPRIMANDS)}
Репутация: {get_val(row, COL_REPUTATION)}
Неактивы: {get_val(row, COL_INACTIVES)}
Дни на должности: {get_val(row, COL_DAYS)}"""

print("Бот запущен!")

for event in longpoll.listen():
    if event.type != VkEventType.MESSAGE_NEW or not event.to_me or not event.text:
        continue
    
    # Защита от дублей по message_id
    msg_id = event.message_id
    if msg_id in PROCESSED_MESSAGES:
        continue
    PROCESSED_MESSAGES.add(msg_id)
    
    # Очистка старых ID (чтобы не забивать память)
    if len(PROCESSED_MESSAGES) > 1000:
        PROCESSED_MESSAGES.clear()
    
    text = event.text.strip()
    user_id = event.user_id
    chat_id = event.chat_id if hasattr(event, 'chat_id') else None
    is_chat = chat_id is not None
    
    if text.lower() == "/id":
        vk.messages.send(user_id=user_id, random_id=get_random_id(), message=f"Ваш ID: {user_id}")
        continue
    
    if text.lower() == "/chatid":
        if is_chat:
            vk.messages.send(chat_id=chat_id, random_id=get_random_id(), message=f"ID беседы: {chat_id}")
        else:
            vk.messages.send(user_id=user_id, random_id=get_random_id(), message=f"Ваш ID: {user_id}")
        continue
    
    if text.lower() == "начать" and not is_chat:
        states = load_json("user_states.json")
        states[str(user_id)] = "waiting_nickname"
        save_json("user_states.json", states)
        vk.messages.send(
            user_id=user_id, random_id=get_random_id(),
            message="Приветствую, администратор! Для начала работы нужно пройти систему подтверждений.\n\n"
                    "Напишите свой никнейм и ожидайте, пока заявку одобрит руководство."
        )
        continue
    
    states = load_json("user_states.json")
    if str(user_id) in states and states[str(user_id)] == "waiting_nickname" and not is_chat:
        nickname = text
        pending = load_json("pending.json")
        pending[str(user_id)] = nickname
        save_json("pending.json", pending)
        del states[str(user_id)]
        save_json("user_states.json", states)
        vk.messages.send(
            chat_id=CHAT_ID, random_id=get_random_id(),
            message=f"🔔 Новая заявка!\n\nID: {user_id}\nНикнейм: {nickname}\n\n/подтвердить {user_id} — одобрить\n/отклонить {user_id} — отклонить"
        )
        vk.messages.send(
            user_id=user_id, random_id=get_random_id(),
            message="✅ Ваша заявка успешно отправлена, ожидайте подтверждения."
        )
        continue
    
    if text.lower().startswith("/подтвердить"):
        parts = text.split()
        if len(parts) != 2:
            vk.messages.send(user_id=user_id, random_id=get_random_id(), message="❗ Используйте: /подтвердить ID")
            continue
        try:
            target_id = int(parts[1])
        except:
            vk.messages.send(user_id=user_id, random_id=get_random_id(), message="❌ Неверный ID")
            continue
        pending = load_json("pending.json")
        if str(target_id) not in pending:
            vk.messages.send(user_id=user_id, random_id=get_random_id(), message=f"❌ Заявка с ID {target_id} не найдена")
            continue
        nickname = pending[str(target_id)]
        approved = load_json("approved.json")
        approved[str(target_id)] = nickname
        save_json("approved.json", approved)
        del pending[str(target_id)]
        save_json("pending.json", pending)
        if is_chat:
            vk.messages.send(chat_id=chat_id, random_id=get_random_id(), message=f"✅ {nickname} (ID: {target_id}) подтверждён!")
        vk.messages.send(user_id=target_id, random_id=get_random_id(), message=f"✅ Ваша заявка подтверждена!\nНикнейм: {nickname}\nТеперь вам доступна команда /stats")
        continue
    
    if text.lower().startswith("/отклонить"):
        parts = text.split()
        if len(parts) != 2:
            vk.messages.send(user_id=user_id, random_id=get_random_id(), message="❗ Используйте: /отклонить ID")
            continue
        try:
            target_id = int(parts[1])
        except:
            vk.messages.send(user_id=user_id, random_id=get_random_id(), message="❌ Неверный ID")
            continue
        pending = load_json("pending.json")
        if str(target_id) not in pending:
            vk.messages.send(user_id=user_id, random_id=get_random_id(), message=f"❌ Заявка с ID {target_id} не найдена")
            continue
        nickname = pending[str(target_id)]
        del pending[str(target_id)]
        save_json("pending.json", pending)
        if is_chat:
            vk.messages.send(chat_id=chat_id, random_id=get_random_id(), message=f"❌ {nickname} (ID: {target_id}) отклонён")
        vk.messages.send(user_id=target_id, random_id=get_random_id(), message="❌ Ваша заявка отклонена руководством.")
        continue
    
    if text.lower() == "/stats" and not is_chat:
        approved = load_json("approved.json")
        if str(user_id) not in approved:
            vk.messages.send(user_id=user_id, random_id=get_random_id(), message="❌ У вас нет доступа. Напишите «Начать» для регистрации.")
            continue
        nickname = approved[str(user_id)]
        try:
            data = get_sheet_data()
            row = find_admin(data, nickname)
            if row:
                reply = format_stats(row)
            else:
                reply = f"❌ Никнейм «{nickname}» не найден в таблице"
        except Exception as e:
            reply = f"❌ Ошибка: {e}"
        vk.messages.send(user_id=user_id, random_id=get_random_id(), message=reply)
        continue
