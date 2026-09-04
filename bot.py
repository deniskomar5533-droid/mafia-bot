import os
import random
from flask import Flask
import telebot
from telebot import types

# ================= НАСТРОЙКИ И ТОКЕН =================
# Вставь сюда свой токен бота, если он не подтягивается из переменных окружения
TOKEN = os.environ.get("BOT_TOKEN", "ТВОЙ_ТОКЕН_БОТА")
bot = telebot.TeleBot(TOKEN)

# ================= ВСЕ 17 РОЛЕЙ =================
ALL_ROLES = [
    "Мафия",
    "Дон мафии",
    "Мирный житель",
    "Шериф",
    "Доктор",
    "Маньяк",
    "Любовница",
    "Журналист",
    "Адвокат",
    "Бессмертный",
    "Путана",
    "Комиссар",
    "Террорист",
    "Ниндзя",
    "Свидетель",
    "Мафия-одиночка",
    "Мэр",
]

# Глобальное состояние игры и лобби
games = {}  # chat_id -> game_data


def get_default_roles_count(total_players):
  """Автоматическое распределение ролей в зависимости от числа игроков"""
  counts = {role: 0 for role in ALL_ROLES}
  counts["Мирный житель"] = max(1, total_players // 3)
  counts["Мафия"] = max(1, total_players // 4)
  counts["Шериф"] = 1
  counts["Доктор"] = 1

  # Остаток добиваем мирными или другими ролями
  assigned = sum(counts.values())
  if assigned < total_players:
    counts["Мирный житель"] += total_players - assigned
  return counts


# ================= КОМАНДЫ СТАРТА И ЛОББИ =================


@bot.message_handler(commands=["start"])
def cmd_start(message):
  bot.reply_to(
      message,
      "Привет! Я бот для игры в Мафию.\nДобавь меня в группу и напиши"
      " `/mafia`, чтобы собрать игру!",
  )


@bot.message_handler(commands=["mafia"])
def cmd_mafia(message):
  chat_id = message.chat.id

  if message.chat.type == "private":
    bot.reply_to(message, "Эту команду нужно использовать в групповом чате!")
    return

  if chat_id in games:
    bot.reply_to(message, "Лобби уже создано! Присоединяйтесь ниже.")
    return

  # Инициализация нового лобби
  games[chat_id] = {
      "host_id": message.from_user.id,
      "players": {
          message.from_user.id: message.from_user.first_name
      },  # id -> name
      "roles_config": {role: 0 for role in ALL_ROLES},
      "state": "lobby",  # lobby, roles_setup, playing
      "lobby_message_id": None,
      "roles_menu_open": False,
  }
  games[chat_id]["roles_config"]["Мирный житель"] = 1
  games[chat_id]["roles_config"]["Мафия"] = 1

  update_lobby(chat_id)


def update_lobby(chat_id):
  game = games.get(chat_id)
  if not game or game["state"] != "lobby":
    return

  players_list = "\n".join(
      [f"▫️ {name}" for uid, name in game["players"].items()]
  )
  total = len(game["players"])

  text = (
      f"🎮 **Сбор игроков в Мафию!**\n\n"
      f"👥 Игроков в лобби: {total}\n"
      f"{players_list}\n\n"
      "Нажмите кнопку ниже, чтобы присоединиться!"
  )

  markup = types.InlineKeyboardMarkup()
  markup.add(
      types.InlineKeyboardButton("🎯 Войти в игру", callback_data="join_game")
  )
  markup.add(
      types.InlineKeyboardButton(
          "⚙️ Настроить роли (17)", callback_data="open_roles_menu"
      )
  )
  markup.add(
      types.InlineKeyboardButton(
          "⏱ +30 секунд", callback_data="add_time"
      ),
      types.InlineKeyboardButton(
          "🚀 Запустить принудительно", callback_data="force_start"
      ),
  )

  if game["lobby_message_id"]:
    try:
      bot.edit_message_text(
          text,
          chat_id,
          game["lobby_message_id"],
          reply_markup=markup,
          parse_mode="Markdown",
      )
    except Exception:
      pass
  else:
    msg = bot.send_message(
        chat_id, text, reply_markup=markup, parse_mode="Markdown"
    )
    game["lobby_message_id"] = msg.message_id


# ================= КНОПКИ И УПРАВЛЕНИЕ ЛОББИ =================


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
  chat_id = call.message.chat.id
  uid = call.from_user.id
  game = games.get(chat_id)

  if not game:
    bot.answer_callback_query(call.id, "Игра не найдена или уже завершена.")
    return

  # 1. Присоединение к игре
  if call.data == "join_game":
    if uid in game["players"]:
      bot.answer_callback_query(call.id, "Вы уже в игре!", show_alert=True)
    else:
      game["players"][uid] = call.from_user.first_name
      bot.answer_callback_query(call.id, "Вы успешно вошли в лобби!")
      update_lobby(chat_id)

  # 2. Открытие меню настройки ролей
  elif call.data == "open_roles_menu":
    if uid != game["host_id"]:
      bot.answer_callback_query(
          call.id, "Только создатель может настраивать роли!", show_alert=True
      )
      return
    game["roles_menu_open"] = True
    show_roles_menu(chat_id, call.message.message_id)

  # 3. Закрытие меню ролей
  elif call.data == "roles_done":
    if uid != game["host_id"]:
      return
    game["roles_menu_open"] = False
    update_lobby(chat_id)

  # 4. Изменение конкретной роли (+ / -)
  elif call.data.startswith("add_") or call.data.startswith("rm_"):
    if uid != game["host_id"]:
      bot.answer_callback_query(call.id, "Только для создателя!", show_alert=True)
      return
    action, role_idx = call.data.split("_", 1)
    role_idx = int(role_idx)
    role_name = ALL_ROLES[role_idx]

    if action == "add":
      game["roles_config"][role_name] += 1
    elif action == "rm" and game["roles_config"][role_name] > 0:
      game["roles_config"][role_name] -= 1

    show_roles_menu(chat_id, call.message.message_id)

  # 5. Кнопка +30 секунд (имитация продления таймера)
  elif call.data == "add_time":
    bot.answer_callback_query(
        call.id, "⏱ Время сбора продлено на 30 секунд!"
    )

  # 6. Принудительный запуск
  elif call.data == "force_start":
    if uid != game["host_id"]:
      bot.answer_callback_query(
          call.id, "Только создатель может запустить игру!", show_alert=True
      )
      return
    start_game(chat_id)


def show_roles_menu(chat_id, message_id):
  game = games.get(chat_id)
  text = "⚙️ **Настройка ролей (из 17 доступных):**\nНажимайте плюс/минус для каждого персонажа:\n\n"

  markup = types.InlineKeyboardMarkup(row_width=3)

  for idx, role in enumerate(ALL_ROLES):
    count = game["roles_config"].get(role, 0)
    text += f"• {role}: `{count}`\n"
    # Кнопки управления количеством роли
    btn_minus = types.InlineKeyboardButton(
        f"➖ {role[:8]}", callback_data=f"rm_{idx}"
    )
    btn_count = types.InlineKeyboardButton(f"{count}", callback_data="noop")
    btn_plus = types.InlineKeyboardButton(
        f"➕ {role[:8]}", callback_data=f"add_{idx}"
    )
    markup.add(btn_minus, btn_count, btn_plus)

  markup.add(
      types.InlineKeyboardButton("✅ Готово (Назад в лобби)", callback_data="roles_done")
  )

  try:
    bot.edit_message_text(
        text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown"
    )
  except Exception:
    pass


def start_game(chat_id):
  game = games.get(chat_id)
  if not game:
    return

  if len(game["players"]) < 3:
    bot.send_message(
        chat_id, "⚠️ Для игры нужно минимум 3 участника!"
    )
    return

  game["state"] = "playing"
  players_ids = list(game["players"].keys())
  random.shuffle(players_ids)

  # Раздача ролей на основе настроек
  active_roles = []
  for role, count in game["roles_config"].items():
    active_roles.extend([role] * count)

  # Если ролей меньше, чем игроков, добиваем мирными
  while len(active_roles) < len(players_ids):
    active_roles.items("Мирный житель")
    active_roles.append("Мирный житель")

  bot.send_message(
      chat_id,
      "🎲 **Игра начинается!** Роли распределены в личные сообщения каждому"
      " участнику. Наступает ночь...",
      parse_mode="Markdown",
  )

  for i, uid in enumerate(players_ids):
    role = (
        active_roles[i] if i < len(active_roles) else "Мирный житель"
    )
    try:
      bot.send_message(uid, f"🎭 Ваша секретная роль в игре: **{role}**", parse_mode="Markdown")
    except Exception:
      # Если игрок не написал боту в ЛС
      pass


# ================= ВЕБ-СЕРВЕР ДЛЯ 24/7 (Flask) =================
app = Flask(__name__)


@app.route("/")
def home():
  return "Mafia Bot is running 24/7!"


# Запуск бота и веб-сервера одновременно
if __name__ == "__main__":
  # Запуск веб-сервера на порту для Render / Koyeb
  port = int(os.environ.get("PORT", 5000))

  import threading

  # Запускаем Flask в отдельном потоке
  threading.Thread(
      target=lambda: app.run(host="0.0.0.0", port=port)
  ).start()

  # Запуск телеграм-бота
  print("Бот запущен...")
  bot.infinity_polling(skip_pending=True)
import os
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
    
