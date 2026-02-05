import telebot
import sqlite3
import os
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

TOKEN = "8299647254:AAHpMGOki7F4xLt7E360h9VD235jb-DIST4"
bot = telebot.TeleBot(TOKEN, threaded=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_BOY = os.path.join(BASE_DIR, "boy.db")
DB_WOMEN = os.path.join(BASE_DIR, "women.db")

# ====== Підключення до баз даних ======
def get_conn1():
    return sqlite3.connect(DB_BOY)

def get_conn2():
    return sqlite3.connect(DB_WOMEN)

# ====== Ініціалізація баз ======
def init_db(conn_func):
    conn = conn_func()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        photo_file_id TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS used (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        photo_file_id TEXT
    )
    """)
    conn.commit()
    conn.close()

init_db(get_conn1)
init_db(get_conn2)

# ====== Стани користувачів ======
user_state = {}
user_name = {}
user_gender = {}

# ====== Клавіатура вибору ======
def regist_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    boy_btn = KeyboardButton("🧑🏻Хлопець")
    women_btn = KeyboardButton("👩🏻Дівчина")
    markup.row(boy_btn, women_btn)
    return markup

# ====== Функція для збереження у базу з перевіркою дубліката ======
def save_to_queue(user_id, name, photo_file_id, conn_func):
    conn = conn_func()
    cur = conn.cursor()

    # Перевірка: чи вже є такий користувач з таким ім'ям
    cur.execute("SELECT id FROM queue WHERE user_id = ? AND name = ?", (user_id, name))
    result = cur.fetchone()

    if result:
        print(f"❌ Користувач {name} з user_id {user_id} вже є в базі!")
        conn.close()
        return False  # запис не додано

    # Додаємо запис
    cur.execute(
        "INSERT INTO queue(user_id, name, photo_file_id) VALUES (?, ?, ?)",
        (user_id, name, photo_file_id)
    )
    conn.commit()
    print(f"✅ {name} успішно додано до бази {conn_func.__name__}")
    conn.close()
    return True  # успішне додавання

# ====== Старт бота ======
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id

    # Перевіряємо, чи користувач вже є у boy.db
    conn_boy = get_conn1()
    cur_boy = conn_boy.cursor()
    cur_boy.execute("SELECT id FROM queue WHERE user_id = ?", (user_id,))
    boy_exists = cur_boy.fetchone()
    conn_boy.close()

    # Перевіряємо, чи користувач вже є у women.db
    conn_women = get_conn2()
    cur_women = conn_women.cursor()
    cur_women.execute("SELECT id FROM queue WHERE user_id = ?", (user_id,))
    women_exists = cur_women.fetchone()
    conn_women.close()

    if boy_exists or women_exists:
        bot.send_message(message.chat.id, "Ви вже зареєстровані в системі! ✅")
        return  # користувач вже є, не реєструємо повторно

    # Якщо користувача ще немає, запускаємо процес реєстрації
    user_state[message.chat.id] = "select_gender"
    bot.send_message(
        message.chat.id,
        f"Привіт {message.from_user.first_name}! Оберіть свій гендер:",
        reply_markup=regist_keyboard()
    )

# ====== Обробка вибору гендеру ======
@bot.message_handler(func=lambda message: user_state.get(message.chat.id) == "select_gender")
def select_gender(message):
    if message.text == "🧑🏻Хлопець":
        user_gender[message.chat.id] = "boy"
    elif message.text == "👩🏻Дівчина":
        user_gender[message.chat.id] = "women"
    else:
        bot.send_message(message.chat.id, "Будь ласка, оберіть один з варіантів!",reply_markup=regist_keyboard())

        return

    user_state[message.chat.id] = "entering_name"
    bot.send_message(message.chat.id, "Введіть ваше ім'я:", reply_markup=ReplyKeyboardRemove())

# ====== Обробка введення імені ======
@bot.message_handler(func=lambda message: user_state.get(message.chat.id) == "entering_name")
def enter_name(message):
    name = message.text.strip()
    if not name:
        bot.send_message(message.chat.id, "Ім'я не може бути порожнім. Спробуйте ще раз:")
        return

    user_name[message.chat.id] = name
    user_state[message.chat.id] = "waiting_photo"
    bot.send_message(message.chat.id, "Тепер надішліть свою фотографію:")

# ====== Обробка фото ======
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    if user_state.get(message.chat.id) != "waiting_photo":
        bot.send_message(message.chat.id, "Будь ласка, спочатку пройдіть реєстрацію командою /start")
        return

    file_id = message.photo[-1].file_id
    name = user_name.get(message.chat.id)
    gender = user_gender.get(message.chat.id)

    conn_func = get_conn1 if gender == "boy" else get_conn2

    success = save_to_queue(message.from_user.id, name, file_id, conn_func)

    if success:
        bot.send_message(message.chat.id, "Ваша фотографія успішно додана! ✅")
    else:
        bot.send_message(message.chat.id, "Такий користувач вже є! ❌")

    # Очистка стану
    user_state.pop(message.chat.id, None)
    user_name.pop(message.chat.id, None)
    user_gender.pop(message.chat.id, None)

print("Bot started...")
bot.infinity_polling(skip_pending=True)
