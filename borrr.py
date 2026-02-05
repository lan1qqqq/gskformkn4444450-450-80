import telebot
from telebot import types
import datetime
import os
import json
import time
import re

# ------------------------ НАСТРОЙКИ ------------------------
BOT_TOKEN = "8228619766:AAGDrBrT9soRRHKpduaXKLtkThCM1avYrAg"
ADMIN_ID = 1400742236

bot = telebot.TeleBot(BOT_TOKEN)

# ------------------------ ПАПКИ И ФАЙЛЫ ------------------------
SCHEDULE_DIR = "schedules"
CHANGES_DIR = "changes"
os.makedirs(SCHEDULE_DIR, exist_ok=True)
os.makedirs(CHANGES_DIR, exist_ok=True)

USERS_FILE = "users.json"
CLASSES_FILE = "classes.json"
CALLS_FILE = "calls.jpg"
MENU_FILE = "menu.jpg"
CHANGES_FILE = os.path.join(CHANGES_DIR, "current.jpg")

# ------------------------ СОСТОЯНИЯ ------------------------
user_states = {}

# ------------------------ УТИЛИТЫ ------------------------
def load_json(file_path, default):
    if not os.path.exists(file_path):
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
        return default
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_json(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_users():
    return load_json(USERS_FILE, {})

def save_users(users):
    save_json(USERS_FILE, users)

def load_classes():
    return load_json(CLASSES_FILE, {"10А": {}, "10Б": {}})

def save_classes(classes):
    save_json(CLASSES_FILE, classes)

def normalize_schedule_lines(raw_lines):
    fixed = []
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            fixed.append(line)
        else:
            parts = re.split(r'(?=\d+\.)', line)
            for p in parts:
                p = p.strip()
                if p:
                    fixed.append(p)
    return fixed

def append_log(text):
    try:
        with open("bot.log", "a", encoding="utf-8") as lf:
            lf.write(f"{datetime.datetime.now().isoformat()} {text}\n")
    except:
        pass

def notify_all_users_changes(file_path, batch_delay=0.12, dry_run=False):
    users = load_users()
    if not users:
        append_log("Broadcast aborted: users.json пустой")
        return 0, list(users.keys())
    sent = 0
    failed = []
    for uid_str in list(users.keys()):
        try:
            chat_id = int(uid_str)
        except:
            failed.append(uid_str)
            append_log(f"Invalid uid in users.json: {uid_str}")
            continue
        if dry_run:
            append_log(f"Dry-run: would send to {chat_id}")
            continue
        try:
            bot.send_message(chat_id, "❗Новые изменения❗")
            with open(file_path, "rb") as imgf:
                bot.send_photo(chat_id, imgf)
            sent += 1
            append_log(f"Sent changes to {chat_id}")
            time.sleep(batch_delay)
        except Exception as e:
            failed.append(uid_str)
            append_log(f"Send error to {uid_str}: {repr(e)}")
            continue
    return sent, failed

# ------------------------ МЕНЮ ------------------------
def main_menu(chat_id_or_message, is_admin=False, show_create_class=False):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📋 Расписание", "🔔 Звонки")
    kb.add("🍽 Школьное меню", "❗ Изменения")
    kb.add("➕ Предложить изменения")
    if show_create_class:
        kb.add("➕ Создать класс")
    if is_admin:
        kb.add("📷 Загрузить изменения", "🍽 Загрузить меню", "📢 Отправить объявление")
    if isinstance(chat_id_or_message, int):
        bot.send_message(chat_id_or_message, "Выбери действие:", reply_markup=kb)
    else:
        bot.send_message(chat_id_or_message.chat.id, "Выбери действие:", reply_markup=kb)

# ------------------------ СТАРТ ------------------------
@bot.message_handler(commands=['start'])
def start(message):
    users = load_users()
    classes = load_classes()
    uid = str(message.from_user.id)
    if uid not in users:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        for c in classes:
            kb.add(c)
        kb.add("➕ Создать класс")
        bot.send_message(message.chat.id, "Привет! Выбери свой класс или создай новый:", reply_markup=kb)
        user_states[uid] = "choose_class"
    else:
        main_menu(message, message.from_user.id == ADMIN_ID, show_create_class=False)

# ------------------------ ВЫБОР КЛАССА ------------------------
@bot.message_handler(func=lambda m: user_states.get(str(m.from_user.id)) == "choose_class")
def choose_class(message):
    uid = str(message.from_user.id)
    text = message.text.strip()
    classes = load_classes()
    users = load_users()
    if text == "➕ Создать класс":
        bot.send_message(message.chat.id, "Напиши новый класс (пример: 7А):")
        user_states[uid] = "create_class"
        return
    if text not in classes:
        bot.send_message(message.chat.id, "Такого класса нет.")
        return
    users[uid] = text
    save_users(users)
    user_states.pop(uid)
    main_menu(message, message.from_user.id == ADMIN_ID, show_create_class=False)

# ------------------------ СОЗДАНИЕ КЛАССА ------------------------
@bot.message_handler(func=lambda m: user_states.get(str(m.from_user.id)) == "create_class")
def create_class(message):
    uid = str(message.from_user.id)
    name = message.text.strip()
    if not re.match(r"^\d+[А-Я]$", name):
        bot.send_message(message.chat.id, "Название класса должно быть типа 7А. Попробуй снова:")
        return
    classes = load_classes()
    if name in classes:
        bot.send_message(message.chat.id, "Такой класс уже существует.")
        return
    classes[name] = {"owner": uid}
    save_classes(classes)
    users = load_users()
    users[uid] = name
    save_users(users)
    user_states.pop(uid)
    bot.send_message(message.chat.id, f"Класс {name} создан!")
    main_menu(message, message.from_user.id == ADMIN_ID, show_create_class=False)

# ------------------------ РАСПИСАНИЕ ------------------------
@bot.message_handler(func=lambda m: m.text == "📋 Расписание")
def show_schedule_menu(message):
    uid = str(message.from_user.id)
    users = load_users()
    if uid not in users:
        bot.send_message(message.chat.id, "Сначала выбери класс через /start")
        return
    cls = users[uid]
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    now = datetime.datetime.now()
    today_weekday = now.weekday()  # 0-Пн, 6-Вс
    if today_weekday >= 5:
        tomorrow_label = "Понедельник"
    else:
        tomorrow_label = "Завтра"
    kb.add("Сегодня", tomorrow_label)
    kb.add("Вся неделя")
    bot.send_message(message.chat.id, "Выбери день:", reply_markup=kb)
    user_states[uid] = "schedule_choice"

# ------------------------ ОБРАБОТКА ВЫБОРА ------------------------
@bot.message_handler(func=lambda m: user_states.get(str(m.from_user.id)) == "schedule_choice")
def handle_schedule_choice(message):
    uid = str(message.from_user.id)
    choice = message.text.strip()
    users = load_users()
    cls = users.get(uid)
    if not cls:
        bot.send_message(message.chat.id, "Сначала выбери класс через /start")
        user_states.pop(uid)
        return
    path = os.path.join(SCHEDULE_DIR, f"{cls}.txt")
    if not os.path.exists(path):
        bot.send_message(message.chat.id,
            "❗ У класса нет расписания.\nНапиши его прямо сюда по примеру:\n\n"
            "# Понедельник\n0. Классный час\n2. Русский\n\n# Вторник\n1. История"
        )
        user_states[uid] = "write_schedule"
        return

    with open(path, "r", encoding="utf-8") as f:
        raw = f.readlines()
    lines = normalize_schedule_lines(raw)

    days = ["Понедельник","Вторник","Среда","Четверг","Пятница","Суббота"]
    blocks = {}
    cur = None
    for l in lines:
        if l.startswith("#"):
            cur = l[1:].strip()
            blocks[cur] = []
        else:
            if cur:
                blocks[cur].append(l)

    # Вся неделя
    if choice == "Вся неделя":
        out = []
        for d in days:
            if d in blocks and blocks[d]:
                out.append(f"*{d}:*\n" + "\n".join(blocks[d]))
            else:
                out.append(f"*{d}:* — нет расписания")
        bot.send_message(message.chat.id, "📋 Расписание на всю неделю для класса " + cls + ":\n\n" + "\n\n".join(out), parse_mode="Markdown")
        main_menu(message, message.from_user.id == ADMIN_ID)
        user_states.pop(uid, None)
        return

    # Сегодня / Завтра
    now = datetime.datetime.now()
    today_idx = now.weekday()
    if choice == "Сегодня":
        target_idx = today_idx if today_idx < 6 else 0
    else:  # Завтра
        target_idx = 0 if today_idx >= 5 else today_idx + 1
    day = days[target_idx]
    if day in blocks and blocks[day]:
        bot.send_message(message.chat.id, f"📋 Расписание для {cls} на {day}:\n" + "\n".join(blocks[day]))
    else:
        bot.send_message(message.chat.id, f"{day}: нет расписания")
    main_menu(message, message.from_user.id == ADMIN_ID)
    user_states.pop(uid, None)

# ------------------------ СОХРАНЕНИЕ РАСПИСАНИЯ ------------------------
@bot.message_handler(func=lambda m: user_states.get(str(m.from_user.id)) == "write_schedule")
def save_schedule(message):
    uid = str(message.from_user.id)
    users = load_users()
    cls = users[uid]
    path = os.path.join(SCHEDULE_DIR, f"{cls}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(message.text)
    bot.send_message(message.chat.id, "✅ Расписание сохранено")
    main_menu(message, message.from_user.id == ADMIN_ID)
    user_states.pop(uid, None)

# ------------------------ ЗВОНКИ ------------------------
@bot.message_handler(func=lambda m: m.text == "🔔 Звонки")
def show_calls(message):
    if os.path.exists(CALLS_FILE):
        bot.send_photo(message.chat.id, open(CALLS_FILE, "rb"))
    else:
        bot.send_message(message.chat.id, "Звонки ещё не добавлены!")
    main_menu(message, message.from_user.id == ADMIN_ID)

# ------------------------ МЕНЮ ------------------------
@bot.message_handler(func=lambda m: m.text == "🍽 Школьное меню")
def show_menu(message):
    if os.path.exists(MENU_FILE):
        bot.send_photo(message.chat.id, open(MENU_FILE, "rb"))
    else:
        bot.send_message(message.chat.id, "Меню ещё не загружено.")
    main_menu(message, message.from_user.id == ADMIN_ID)

# ------------------------ ИЗМЕНЕНИЯ ------------------------
@bot.message_handler(func=lambda m: m.text == "❗ Изменения")
def show_changes(message):
    if os.path.exists(CHANGES_FILE):
        try:
            bot.send_photo(message.chat.id, open(CHANGES_FILE, "rb"))
        except:
            bot.send_message(message.chat.id, "Ошибка при отправке файла изменений.")
    else:
        bot.send_message(message.chat.id, "Изменений пока нет.")
    main_menu(message, message.from_user.id == ADMIN_ID)

# ------------------------ ПРЕДЛОЖКА ИЗМЕНЕНИЙ ------------------------
@bot.message_handler(func=lambda m: m.text == "➕ Предложить изменения")
def suggest_changes(message):
    user_states[message.from_user.id] = "wait_user_photo"
    bot.send_message(message.chat.id, "📸 Отправь фото изменений")

@bot.message_handler(content_types=["photo"])
def handle_user_photo(message):
    uid = message.from_user.id
    state = user_states.get(uid)
    if state != "wait_user_photo":
        return
    user_states.pop(uid)
    file_id = message.photo[-1].file_id
    file_info = bot.get_file(file_id)
    downloaded = bot.download_file(file_info.file_path)
    temp_path = os.path.join(CHANGES_DIR, f"temp_{uid}.jpg")
    with open(temp_path, "wb") as f:
        f.write(downloaded)
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("✅ Одобрить", callback_data=f"approve:{uid}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject:{uid}")
    )
    with open(temp_path, "rb") as img:
        bot.send_photo(
            ADMIN_ID,
            img,
            caption=f"📩 Новое предложение изменений\nОт пользователя: @{message.from_user.username or uid}",
            reply_markup=kb
        )
    bot.send_message(message.chat.id, "✅ Отправлено администрации")
    main_menu(message, message.from_user.id == ADMIN_ID)

# ------------------------ INLINE КНОПКИ ------------------------
@bot.callback_query_handler(func=lambda c: c.data.startswith(("approve", "reject")))
def handle_decision(call):
    if call.from_user.id != ADMIN_ID:
        return
    parts = call.data.split(":")
    action = parts[0]
    uid = parts[1]
    if action == "reject":
        bot.edit_message_caption("❌ Отклонено", call.message.chat.id, call.message.message_id)
        return
    temp_path = os.path.join(CHANGES_DIR, f"temp_{uid}.jpg")
    if os.path.exists(temp_path):
        with open(CHANGES_FILE, "wb") as f:
            with open(temp_path, "rb") as img:
                f.write(img.read())
        sent, failed = notify_all_users_changes(CHANGES_FILE)
        bot.edit_message_caption(
            f"✅ Опубликовано\n📤 {sent} | ⚠ {failed}",
            call.message.chat.id,
            call.message.message_id
        )
        os.remove(temp_path)

# ------------------------ АДМИН: ЗАГРУЗКА ИЗМЕНЕНИЙ ------------------------
@bot.message_handler(func=lambda m: m.text == "📷 Загрузить изменения")
def admin_upload(message):
    if message.from_user.id != ADMIN_ID:
        return
    user_states[ADMIN_ID] = "wait_admin_photo"
    bot.send_message(message.chat.id, "📸 Отправь фото для публикации")

# ------------------------ АДМИН: загрузка меню ------------------------
@bot.message_handler(func=lambda m: m.text == "🍽 Загрузить меню")
def load_menu(message):
    if message.from_user.id != ADMIN_ID:
        return
    bot.send_message(message.chat.id, "Отправь фото меню:")
    bot.register_next_step_handler(message, save_menu)

def save_menu(message):
    if message.from_user.id != ADMIN_ID:
        return
    if not message.photo:
        bot.send_message(message.chat.id, "Нужно фото!")
        return
    file_id = message.photo[-1].file_id
    file_info = bot.get_file(file_id)
    downloaded = bot.download_file(file_info.file_path)
    with open(MENU_FILE, "wb") as f:
        f.write(downloaded)
    bot.send_message(message.chat.id, "✅ Меню сохранено!")
    main_menu(message, message.from_user.id == ADMIN_ID)

# ------------------------ АДМИН: ОБЪЯВЛЕНИЯ ------------------------
def cancel_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add("Отменить")
    return kb

@bot.message_handler(func=lambda m: m.text == "📢 Отправить объявление")
def admin_announcement(message):
    if message.from_user.id != ADMIN_ID:
        return
    bot.send_message(message.chat.id, "Напиши текст объявления или нажми 'Отменить':", reply_markup=cancel_keyboard())
    user_states[ADMIN_ID] = "wait_announcement"

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "wait_announcement")
def send_announcement(message):
    if message.from_user.id != ADMIN_ID:
        return
    if message.text == "Отменить":
        user_states.pop(ADMIN_ID)
        bot.send_message(ADMIN_ID, "❌ Отправка объявления отменена", reply_markup=types.ReplyKeyboardRemove())
        main_menu(ADMIN_ID, is_admin=True)
        return
    user_states.pop(ADMIN_ID)
    text = message.text
    users = load_users()
    sent, failed = 0, 0
    for uid in users:
        try:
            bot.send_message(int(uid), f"📢 <b>Объявление:</b>\n{text}", parse_mode="HTML")
            sent += 1
        except:
            failed += 1
    bot.send_message(ADMIN_ID, f"✅ Рассылка завершена.\n📬 Доставлено: {sent}\n⚠ Ошибок: {failed}", reply_markup=types.ReplyKeyboardRemove())
    main_menu(ADMIN_ID, is_admin=True)

# ------------------------ ЗАПУСК ------------------------
bot.polling(none_stop=True)
