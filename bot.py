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

TABLE_URL = "https://docs.google.com/spreadsheets/d/ТВОЙ_ID/edit?usp=sharing"
SHEET_NAME = "Лист1"

CHAT_ID = 1  # ID беседы
# ===================================================

def extract_id(url):
    match = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
    return match.group(1) if match else url

TABLE_ID = extract_id(TABLE_URL)

vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()
longpoll = VkLongPoll(vk_session)

STATES_FILE = "user_states.json"
USERS_FILE = "approved_users.json"
PENDING_FILE = "pending_applications.json"

def load_json(file):
    if os.path.exists(file):
        with open(file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_json(data, file):
    with open(file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_google_sheet():
    """Получает данные из публичной Google Таблицы"""
    url = f"https://docs.google.com/spreadsheets/d/{TABLE_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_NAME}"
    response = requests.get(url)
    response.encoding = 'utf-8'
    return list(csv.reader(StringIO(response.text)))

def find_admin(data, nickname):
    """Ищет админа по никнейму"""
    if not data:
        return None, "❌ Таблица пуста"
    
    headers = data[0]
    rows = data[1:] if len(data) > 1 else []
    
    nickname_col = None
    for i, header in enumerate(headers):
        if header.strip().lower() in ["никнейм администратора", "никнейм", "ник"]:
            nickname_col = i
            break
    
    if nickname_col is None:
        return None, "❌ Столбец с никнеймом не найден"
    
    for row in rows:
        if len(row) > nickname_col and row[nickname_col].strip().lower() == nickname.lower():
            return row, headers
    
    return None, f"❌ Админ «{nickname}» не найден"

def format_admin_stats(row, headers):
    """Форматирует статистику одного админа"""
    data = {}
    for i, header in enumerate(headers):
        if i < len(row):
            data[header.strip().lower()] = row[i]
        else:
            data[header.strip().lower()] = ""
    
    def get_field(*keys):
        for key in keys:
            if key in data:
                return data[key]
        return "—"
    
    nickname = get_field("никнейм администратора", "никнейм", "ник")
    position = get_field("должность")
    extra_position = get_field("доп. должность", "доп должность")
    warnings = get_field("предупреждений", "предупреждения")
    reprimands = get_field("выговоров", "выговоры")
    reputation = get_field("репутация")
    inactives = get_field("неактивы")
    days_on_duty = get_field("дни на должности", "дней на должности")

    message = f"""📊 Статистика администратора:

Никнейм администратора: {nickname}
Должность: {position}
Доп. должность: {extra_position}
Предупреждений: {warnings}
Выговоров: {reprimands}
Репутация: {reputation}
Неактивы: {inactives}
Дни на должности: {days_on_duty}"""
    
    return message

def send_application_to_chat(user_id, nickname):
    """Отправляет заявку в беседу"""
    vk.messages.send(
        chat_id=CHAT_ID,
        random_id=get_random_id(),
        message=f"🔔 Новая заявка на подтверждение!\n\n"
                f"ID пользователя: {user_id}\n"
                f"Никнейм: {nickname}\n\n"
                f"Для подтверждения: /подтвердить {user_id}\n"
                f"Для отклонения: /отклонить {user_id}"
    )
    
    pending = load_json(PENDING_FILE)
    pending[str(user_id)] = {
        "nickname": nickname,
        "status": "ожидает"
    }
    save_json(pending, PENDING_FILE)

def approve_application(user_id, nickname):
    """Подтверждает заявку"""
    approved = load_json(USERS_FILE)
    approved[str(user_id)] = nickname
    save_json(approved, USERS_FILE)
    
    pending = load_json(PENDING_FILE)
    if str(user_id) in pending:
        del pending[str(user_id)]
        save_json(pending, PENDING_FILE)
    
    vk.messages.send(
        user_id=user_id,
        random_id=get_random_id(),
        message=f"✅ Ваша заявка подтверждена!\n"
                f"Ваш никнейм: {nickname}\n"
                f"Теперь вам доступна команда /stats"
    )

def reject_application(user_id, nickname):
    """Отклоняет заявку"""
    pending = load_json(PENDING_FILE)
    if str(user_id) in pending:
        del pending[str(user_id)]
        save_json(pending, PENDING_FILE)
    
    vk.messages.send(
        user_id=user_id,
        random_id=get_random_id(),
        message=f"❌ Ваша заявка отклонена руководством."
    )

def get_user_nickname(user_id):
    """Получает никнейм подтверждённого пользователя"""
    approved = load_json(USERS_FILE)
    return approved.get(str(user_id))

def get_pending_user(user_id):
    """Получает данные ожидающей заявки"""
    pending = load_json(PENDING_FILE)
    return pending.get(str(user_id))

print("Бот запущен...")

for event in longpoll.listen():
    if event.type == VkEventType.MESSAGE_NEW and event.to_me and event.text:
        text = event.text.strip()
        user_id = event.user_id
        chat_id = event.chat_id if hasattr(event, 'chat_id') else None
        
        states = load_json(STATES_FILE)
        
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
            if chat_id:
                reply = f"ID этой беседы: {chat_id}"
            else:
                reply = f"Эта команда работает только в беседе. Ваш ID: {user_id}"
            vk.messages.send(
                user_id=user_id,
                random_id=get_random_id(),
                message=reply
            )
            continue
        
        # ==================== НАЧАТЬ (только в ЛС) ====================
        if text.lower() == "начать":
            states[str(user_id)] = {"state": "waiting_nickname"}
            save_json(states, STATES_FILE)
            
            vk.messages.send(
                user_id=user_id,
                random_id=get_random_id(),
                message="Приветствую, администратор! Для начала работы нужно пройти систему подтверждений.\n\n"
                        "Напишите свой никнейм и ожидайте, пока заявку одобрит руководство."
            )
            continue
        
        # ==================== ОЖИДАНИЕ НИКНЕЙМА (только в ЛС) ====================
        if str(user_id) in states and states[str(user_id)].get("state") == "waiting_nickname":
            nickname = text
            send_application_to_chat(user_id, nickname)
            
            del states[str(user_id)]
            save_json(states, STATES_FILE)
            
            vk.messages.send(
                user_id=user_id,
                random_id=get_random_id(),
                message="✅ Ваша заявка успешно отправлена, ожидайте подтверждения."
            )
            continue
        
        # ==================== /подтвердить ID (в беседе) ====================
        if text.lower().startswith("/подтвердить"):
            parts = text.split()
            if len(parts) == 2:
                try:
                    target_id = int(parts[1])
                    application = get_pending_user(target_id)
                    
                    if application:
                        approve_application(target_id, application["nickname"])
                        reply = f"✅ Заявка {application['nickname']} (ID: {target_id}) подтверждена!"
                    else:
                        reply = f"❌ Заявка с ID {target_id} не найдена."
                except ValueError:
                    reply = "❌ Неверный ID. Используйте: /подтвердить 123456789"
            else:
                reply = "❗ Используйте: /подтвердить ID"
            
            # Отправляем в беседу или в ЛС (в зависимости от того, где команда)
            if chat_id:
                vk.messages.send(chat_id=chat_id, random_id=get_random_id(), message=reply)
            else:
                vk.messages.send(user_id=user_id, random_id=get_random_id(), message=reply)
            continue
        
        # ==================== /отклонить ID (в беседе) ====================
        if text.lower().startswith("/отклонить"):
            parts = text.split()
            if len(parts) == 2:
                try:
                    target_id = int(parts[1])
                    application = get_pending_user(target_id)
                    
                    if application:
                        reject_application(target_id, application["nickname"])
                        reply = f"❌ Заявка {application['nickname']} (ID: {target_id}) отклонена."
                    else:
                        reply = f"❌ Заявка с ID {target_id} не найдена."
                except ValueError:
                    reply = "❌ Неверный ID. Используйте: /отклонить 123456789"
            else:
                reply = "❗ Используйте: /отклонить ID"
            
            if chat_id:
                vk.messages.send(chat_id=chat_id, random_id=get_random_id(), message=reply)
            else:
                vk.messages.send(user_id=user_id, random_id=get_random_id(), message=reply)
            continue
        
        # ==================== /stats (только в ЛС) ====================
        if text.lower() == "/stats":
            nickname = get_user_nickname(user_id)
            
            if not nickname:
                vk.messages.send(
                    user_id=user_id,
                    random_id=get_random_id(),
                    message="❌ У вас нет доступа. Сначала пройдите подтверждение — напишите «Начать»."
                )
                continue
            
            try:
                data = get_google_sheet()
                row, headers = find_admin(data, nickname)
                
                if row is None:
                    reply = headers if headers else "❌ Неизвестная ошибка"
                else:
                    reply = format_admin_stats(row, headers)
                    
            except Exception as e:
                reply = f"❌ Ошибка: {e}"

            vk.messages.send(user_id=user_id, random_id=get_random_id(), message=reply)
            continue
