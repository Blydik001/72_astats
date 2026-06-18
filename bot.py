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
SHEET_NAME = "Июнь 2026"
CHAT_ID = 1  # ID беседы для заявок

# Соответствие букв столбцов индексам (A=0, B=1, C=2, ..., Z=25, AA=26, ...)
# A=0, B=1, C=2, K=10, L=11, AX=49, AY=50, AZ=51
# ===================================================

def col_to_index(col_letter):
    """Переводит букву столбца в индекс: A=0, B=1, ..., Z=25, AA=26, AX=49"""
    result = 0
    for char in col_letter.upper():
        result = result * 26 + (ord(char) - ord('A') + 1)
    return result - 1

# Индексы столбцов
COL_NICKNAME = col_to_index("A")       # Никнейм
COL_POSITION = col_to_index("B")       # Должность
COL_EXTRA_POS = col_to_index("C")      # Доп. должность
COL_WARNINGS = col_to_index("K")       # Предупреждений
COL_REPRIMANDS = col_to_index("L")     # Выговоров
COL_REPUTATION = col_to_index("AX")    # Репутация
COL_INACTIVES = col_to_index("AY")     # Неактивы
COL_DAYS = col_to_index("AZ")          # Дни на должности

match = re.search(r'/d/([a-zA-Z0-9-_]+)', TABLE_URL)
TABLE_ID = match.group(1) if match else TABLE_URL

vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()
longpoll = VkLongPoll(vk_session)

def load_json(filename):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_sheet_data():
    """Читает публичную Google Таблицу"""
    url = f"https://docs.google.com/spreadsheets/d/{TABLE_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_NAME}"
    r = requests.get(url)
    r.encoding = 'utf-8'
    return list(csv.reader(StringIO(r.text)))

def get_cell(row, col_index):
    """Безопасно получает значение ячейки по индексу"""
    if col_index < len(row):
        return row[col_index].strip()
    return "—"

def find_admin(data, nickname):
    """Ищет строку админа по никнейму (столбец A)"""
    if len(data) < 2:
        return None
    
    rows = data[1:]  # Пропускаем заголовки
    
    for row in rows:
        if get_cell(row, COL_NICKNAME).lower() == nickname.lower():
            return row
    
    return None

def format_stats(row):
    """Форматирует статистику"""
    return f"""📊 Статистика администратора:

Никнейм администратора: {get_cell(row, COL_NICKNAME)}
Должность: {get_cell(row, COL_POSITION)}
Доп. должность: {get_cell(row, COL_EXTRA_POS)}
Предупреждений: {get_cell(row, COL_WARNINGS)}
Выговоров: {get_cell(row, COL_REPRIMANDS)}
Репутация: {get_cell(row, COL_REPUTATION)}
Неактивы: {get_cell(row, COL_INACTIVES)}
Дни на должности: {get_cell(row, COL_DAYS)}"""

# ==================== ЗАПУСК ====================
print("Бот запущен!")

for event in longpoll.listen():
    if event.type != VkEventType.MESSAGE_NEW or not event.to_me or not event.text:
        continue
    
    text = event.text.strip()
    user_id = event.user_id
    chat_id = event.chat_id if hasattr(event, 'chat_id') else None
    is_chat = chat_id is not None
    
    # ==================== /id ====================
    if text.lower() == "/id":
        vk.messages.send(
            user_id=user_id,
            random_id=get_random_id(),
            message=f"Ваш ID: {user_id}"
        )
        continue
    
    # ==================== /chatid ====================
    if text.lower() == "/chatid":
        if is_chat:
            vk.messages.send(
                chat_id=chat_id,
                random_id=get_random_id(),
                message=f"ID беседы: {chat_id}"
            )
        else:
            vk.messages.send(
                user_id=user_id,
                random_id=get_random_id(),
                message=f"Ваш ID: {user_id}"
            )
        continue
    
    # ==================== НАЧАТЬ (ЛС) ====================
    if text.lower() == "начать" and not is_chat:
        states = load_json("user_states.json")
        states[str(user_id)] = "waiting_nickname"
        save_json("user_states.json", states)
        
        vk.messages.send(
            user_id=user_id,
            random_id=get_random_id(),
            message="Приветствую, администратор! Для начала работы нужно пройти систему подтверждений.\n\n"
                    "Напишите свой никнейм и ожидайте, пока заявку одобрит руководство."
        )
        continue
    
    # ==================== ВВОД НИКНЕЙМА (ЛС) ====================
    states = load_json("user_states.json")
    if str(user_id) in states and states[str(user_id)] == "waiting_nickname" and not is_chat:
        nickname = text
        
        pending = load_json("pending.json")
        pending[str(user_id)] = nickname
        save_json("pending.json", pending)
        
        del states[str(user_id)]
        save_json("user_states.json", states)
        
        vk.messages.send(
            chat_id=CHAT_ID,
            random_id=get_random_id(),
            message=f"🔔 Новая заявка!\n\n"
                    f"ID: {user_id}\n"
                    f"Никнейм: {nickname}\n\n"
                    f"/подтвердить {user_id} — одобрить\n"
                    f"/отклонить {user_id} — отклонить"
        )
        
        vk.messages.send(
            user_id=user_id,
            random_id=get_random_id(),
            message="✅ Ваша заявка успешно отправлена, ожидайте подтверждения."
        )
        continue
    
    # ==================== /подтвердить ID ====================
    if text.lower().startswith("/подтвердить"):
        parts = text.split()
        
        if len(parts) != 2:
            vk.messages.send(
                user_id=user_id,
                random_id=get_random_id(),
                message="❗ Используйте: /подтвердить ID"
            )
            continue
        
        try:
            target_id = int(parts[1])
        except:
            vk.messages.send(
                user_id=user_id,
                random_id=get_random_id(),
                message="❌ Неверный ID"
            )
            continue
        
        pending = load_json("pending.json")
        
        if str(target_id) not in pending:
            vk.messages.send(
                user_id=user_id,
                random_id=get_random_id(),
                message=f"❌ Заявка с ID {target_id} не найдена"
            )
            continue
        
        nickname = pending[str(target_id)]
        
        approved = load_json("approved.json")
        approved[str(target_id)] = nickname
        save_json("approved.json", approved)
        
        del pending[str(target_id)]
        save_json("pending.json", pending)
        
        if is_chat:
            vk.messages.send(
                chat_id=chat_id,
                random_id=get_random_id(),
                message=f"✅ {nickname} (ID: {target_id}) подтверждён!"
            )
        
        vk.messages.send(
            user_id=target_id,
            random_id=get_random_id(),
            message=f"✅ Ваша заявка подтверждена!\nНикнейм: {nickname}\nТеперь вам доступна команда /stats"
        )
        continue
    
    # ==================== /отклонить ID ====================
    if text.lower().startswith("/отклонить"):
        parts = text.split()
        
        if len(parts) != 2:
            vk.messages.send(
                user_id=user_id,
                random_id=get_random_id(),
                message="❗ Используйте: /отклонить ID"
            )
            continue
        
        try:
            target_id = int(parts[1])
        except:
            vk.messages.send(
                user_id=user_id,
                random_id=get_random_id(),
                message="❌ Неверный ID"
            )
            continue
        
        pending = load_json("pending.json")
        
        if str(target_id) not in pending:
            vk.messages.send(
                user_id=user_id,
                random_id=get_random_id(),
                message=f"❌ Заявка с ID {target_id} не найдена"
            )
            continue
        
        nickname = pending[str(target_id)]
        del pending[str(target_id)]
        save_json("pending.json", pending)
        
        if is_chat:
            vk.messages.send(
                chat_id=chat_id,
                random_id=get_random_id(),
                message=f"❌ {nickname} (ID: {target_id}) отклонён"
            )
        
        vk.messages.send(
            user_id=target_id,
            random_id=get_random_id(),
            message="❌ Ваша заявка отклонена руководством."
        )
        continue
    
    # ==================== /stats (ЛС) ====================
    if text.lower() == "/stats" and not is_chat:
        approved = load_json("approved.json")
        
        if str(user_id) not in approved:
            vk.messages.send(
                user_id=user_id,
                random_id=get_random_id(),
                message="❌ У вас нет доступа. Напишите «Начать» для регистрации."
            )
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
        
        vk.messages.send(
            user_id=user_id,
            random_id=get_random_id(),
            message=reply
        )
        continue
