import os
import random
import threading
import time
from flask import Flask
import telebot
from telebot import types

TOKEN = "8429089487:AAH_jKSvYpoPaD_RTqA6wSh5SynasROZtKo"
bot = telebot.TeleBot(TOKEN)

# --- ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ЛОББИ ---
lobby_active = False
lobby_timer = 0
lobby_chat_id = None
lobby_message_id = None
host_id = None
roles_menu_open = False  # Блокировка обновления экрана при настройке ролей

players = {}  # ID -> {name, role, alive, will}
game_started = False

# Все 17 ролей
DEFAULT_ROLES = {
    "Мафия": 1,
    "Подставной": 0,
    "Дон": 0,
    "Шулер": 0,
    "Доктор": 1,
    "Шериф": 1,
    "Помощник шерифа": 0,
    "Хронос": 0,
    "Шут": 0,
    "Смотрящий": 0,
    "Заражённый": 0,
    "Мститель": 0,
    "Любовница": 0,
    "Медсестра": 0,
    "Маньяк": 0,
    "Имитатор": 0,
    "Мирный житель": 1,
}

selected_roles = DEFAULT_ROLES.copy()


def setup_bot_commands():
  commands = [
      telebot.types.BotCommand("lobby", "⚔️ Создать лобби мафии"),
      telebot.types.BotCommand("reset", "🔄 Сбросить зависшую игру"),
      telebot.types.BotCommand("roles", "📜 Список участников и ролей"),
      telebot.types.BotCommand("will", "✉️ Написать завещание"),
      telebot.types.BotCommand("ping", "🟢 Проверка бота"),
  ]
  try:
    bot.set_my_commands(commands)
  except Exception:
    pass


def get_lobby_keyboard():
  markup = types.InlineKeyboardMarkup()
  btn_join = types.InlineKeyboardButton("⚔️ Войти", callback_data="join_game")
  btn_leave = types.InlineKeyboardButton("🚪 Выйти", callback_data="leave_game")
  btn_roles = types.InlineKeyboardButton(
      "⚙️ Настройка ролей", callback_data="setup_roles"
  )
  btn_start = types.InlineKeyboardButton(
      "🚀 Старт игры", callback_data="force_start"
  )

  markup.add(btn_join, btn_leave)
  markup.add(btn_roles)
  markup.add(btn_start)
  return markup


def get_roles_setup_keyboard():
  markup = types.InlineKeyboardMarkup(row_width=3)
  for role, count in selected_roles.items():
    btn_m = types.InlineKeyboardButton("➖", callback_data=f"rm_{role}")
    btn_i = types.InlineKeyboardButton(f"{role}: {count}", callback_data="noop")
    btn_p = types.InlineKeyboardButton("➕", callback_data=f"rp_{role}")
    markup.add(btn_m, btn_i, btn_p)

  total = sum(selected_roles.values())
  btn_back = types.InlineKeyboardButton(
      f"✅ Сохранить ({total}/{len(players)} карт)", callback_data="roles_done"
  )
  markup.add(btn_back)
  return markup


def update_lobby_message():
  global lobby_active, lobby_timer, lobby_chat_id, lobby_message_id, roles_menu_open

  if not lobby_active or not lobby_message_id or roles_menu_open:
    return

  p_list = (
      "\n".join([f"• `{p['name']}`" for p in players.values()])
      if players
      else "_Пусто..._"
  )
  mins, secs = lobby_timer // 60, lobby_timer % 60
  r_summary = (
      ", ".join([f"{r}: {c}" for r, c in selected_roles.items() if c > 0])
      or "Не выбрано"
  )

  text = (
      "🏙 **ИГРОВОЕ ЛОББИ (MAFIA TOWN)**\n"
      "───────────────────────\n"
      f"⏳ **Время:** `{mins:02d}:{secs:02d}` | 👥 **Участников:**"
      f" `{len(players)}`\n"
      f"⚙️ **Роли:** _{r_summary}_\n\n"
      f"**Состав:**\n{p_list}"
  )

  try:
    bot.edit_message_text(
        text,
        lobby_chat_id,
        lobby_message_id,
        parse_mode="Markdown",
        reply_markup=get_lobby_keyboard(),
    )
  except Exception:
    pass


# --- ПОТОК ТАЙМЕРА ЛОББИ ---
def lobby_timer_countdown():
  global lobby_timer, lobby_active, lobby_chat_id, lobby_message_id, game_started
  while lobby_active and lobby_timer > 0:
    time.sleep(1)
    if not lobby_active or game_started:
      break
    lobby_timer -= 1
    update_lobby_message()

  if lobby_active and lobby_timer <= 0:
    lobby_active = False
    if len(players) >= 3:
      start_game()
    else:
      try:
        bot.send_message(
            lobby_chat_id,
            "⏰ Время вышло, но участников меньше 3. Лобби закрыто.",
        )
      except Exception:
        pass


def start_game():
  global game_started, lobby_active, roles_menu_open
  total_roles = sum(selected_roles.values())

  if total_roles != len(players):
    try:
      bot.send_message(
          lobby_chat_id,
          f"❌ **Ошибка баланса!** Карт ролей ({total_roles}) != участников"
          f" ({len(players)}). Настройте роли под количество игроков!",
          parse_mode="Markdown",
      )
    except Exception:
      pass
    return

  game_started = True
  lobby_active = False
  roles_menu_open = False

  role_deck = []
  for role, count in selected_roles.items():
    role_deck.extend([role] * count)
  random.shuffle(role_deck)

  for (uid, pdata), role in zip(players.items(), role_deck):
    pdata["role"] = role
    pdata["alive"] = True
    pdata["will"] = ""

    try:
      bot.send_message(
          uid,
          f"🎭 **ИГРА НАЧАЛАСЬ!**\n\nТвоя секретная роль: **{role}**",
          parse_mode="Markdown",
      )
    except Exception:
      pass

  try:
    bot.send_message(
        lobby_chat_id,
        "🔥 **Игра началась!** Роли успешно распределены в личные сообщения"
        " участникам.",
        parse_mode="Markdown",
    )
  except Exception:
    pass


# --- КОМАНДЫ ---


@bot.message_handler(commands=["lobby"])
def cmd_lobby(message):
  global lobby_active, lobby_timer, lobby_chat_id, lobby_message_id, players, host_id, selected_roles, game_started

  if message.chat.type == "private":
    bot.reply_to(message, "Эту команду можно использовать только в группе!")
    return

  if game_started or lobby_active:
    bot.reply_to(
        message,
        "⚠️ Игра уже идет или лобби открыто! Если игра зависла, напишите"
        " `/reset`.",
    )
    return

  players = {message.from_user.id: {"name": message.from_user.first_name}}
  selected_roles = DEFAULT_ROLES.copy()
  host_id = message.from_user.id
  lobby_active = True
  lobby_timer = 120
  lobby_chat_id = message.chat.id

  msg = bot.send_message(
      lobby_chat_id,
      "⏳ Создание лобби...",
      parse_mode="Markdown",
      reply_markup=get_lobby_keyboard(),
  )
  lobby_message_id = msg.message_id
  update_lobby_message()

  # Запуск потока таймера
  threading.Thread(target=lobby_timer_countdown, daemon=True).start()


@bot.message_handler(commands=["reset"])
def cmd_reset(message):
  global lobby_active, game_started, players, roles_menu_open
  lobby_active = False
  game_started = False
  roles_menu_open = False
  players.clear()
  bot.reply_to(
      message,
      "🔄 Состояние игры полностью сброшено! Теперь можно снова запустить"
      " `/lobby`.",
  )


@bot.message_handler(commands=["roles"])
def cmd_show_roles(message):
  p_list = (
      "\n".join([
          f"• {p['name']} — {p.get('role', 'Не распределена')}"
          for p in players.values()
      ])
      if players
      else "Лобби пустое."
  )
  bot.reply_to(
      message,
      f"📜 **Список участников и ролей:**\n\n{p_list}",
      parse_mode="Markdown",
  )


@bot.message_handler(commands=["will"])
def cmd_set_will(message):
  if message.chat.type != "private":
    bot.reply_to(
        message,
        "✉️ Пиши завещание мне в **личные сообщения**, чтобы другие игроки не"
        " подсмотрели!",
        parse_mode="Markdown",
    )
    return

  uid = message.from_user.id
  text_parts = message.text.split(maxsplit=1)

  if len(text_parts) < 2:
    bot.reply_to(
        message,
        "⚠️ Напиши текст завещания сразу после команды. Пример:\n`/will Я"
        " считаю что мафия — это игрок`",
        parse_mode="Markdown",
    )
    return

  will_text = text_parts[1]
  user_found = False

  for p_id, pdata in players.items():
    if str(p_id) == str(uid):
      pdata["will"] = will_text
      user_found = True
      break

  if user_found:
    bot.reply_to(
        message,
        f"✅ Завещание успешно сохранено:\n_{will_text}_",
        parse_mode="Markdown",
    )
  else:
    bot.reply_to(message, "❌ Ты не находишься в активной игре!")


@bot.message_handler(commands=["ping"])
def cmd_ping(message):
  bot.reply_to(message, "🟢 Бот активен и работает стабильно!")


# --- ОБРАБОТЧИК КНОПОК ---


@bot.callback_query_handler(func=lambda call: True)
def handle_clicks(call):
  global lobby_active, players, roles_menu_open
  uid = call.from_user.id
  name = call.from_user.first_name

  try:
    bot.answer_callback_query(call.id)
  except Exception:
    pass

  if call.data == "join_game":
    if not lobby_active:
      return
    if uid not in players:
      players[uid] = {"name": name}
      update_lobby_message()

  elif call.data == "leave_game":
    if uid in players:
      del players[uid]
      update_lobby_message()

  elif call.data == "setup_roles":
    if uid != host_id:
      bot.answer_callback_query(
          call.id, "⚠️ Только создатель может настраивать роли!", show_alert=True
      )
      return
    roles_menu_open = True
    try:
      bot.edit_message_text(
          f"⚙️ **НАСТРОЙКА РОЛЕЙ** (Всего участников: {len(players)}):",
          lobby_chat_id,
          lobby_message_id,
          parse_mode="Markdown",
          reply_markup=get_roles_setup_keyboard(),
      )
    except Exception:
      pass

  elif call.data.startswith("rp_"):
    r = call.data.replace("rp_", "")
    selected_roles[r] += 1
    try:
      bot.edit_message_reply_markup(
          lobby_chat_id,
          lobby_message_id,
          reply_markup=get_roles_setup_keyboard(),
      )
    except Exception:
      pass

  elif call.data.startswith("rm_"):
    r = call.data.replace("rm_", "")
    if selected_roles[r] > 0:
      selected_roles[r] -= 1
      try:
        bot.edit_message_reply_markup(
            lobby_chat_id,
            lobby_message_id,
            reply_markup=get_roles_setup_keyboard(),
      )
    except Exception:
      pass

  elif call.data == "roles_done":
    roles_menu_open = False
    update_lobby_message()

  elif call.data == "force_start":
    if uid != host_id:
      bot.answer_callback_query(
          call.id, "⚠️ Только создатель может запустить игру!", show_alert=True
      )
      return
    start_game()


setup_bot_commands()


# ================= ВЕБ-СЕРВЕР ДЛЯ ОБЛАЧНОГО ХОСТИНГА (24/7) =================
app = Flask(__name__)


@app.route("/")
def home():
  return "Mafia Bot is running 24/7!"


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 5000))
  # Запускаем Flask в отдельном потоке, чтобы он не мешал боту
  threading.Thread(target=lambda: app.run(host="0.0.0.0", port=port)).start()

  # Запуск самого телеграм-бота
  print("Бот запущен...")
  bot.infinity_polling(skip_pending=True)
    
