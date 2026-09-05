import random
import threading
import time
import telebot
from telebot import types

TOKEN = "8429089487:AAH_jKSvYpoPaD_RTqA6wSh5SynasROZtKo"
bot = telebot.TeleBot(TOKEN)

# --- ИМЕНА И СЛЕНГ ДЛЯ УМНЫХ ИИ-БОТОВ ---
AI_NAMES = [
    "Тимур",
    "Артём",
    "Данил",
    "Максим",
    "София",
    "Кирилл",
    "Вадим",
    "Алина",
    "Илья",
    "Никита",
    "Дима",
    "Оля",
    "Влад",
    "Егор",
    "Маша",
    "Саша",
]

SLANG_RESPONSES = {
    "suspicious": [
        "Мутный базар, {target}... Где пруфы, что ты мирный?",
        "{target} жестко суетит, это не хисам халяль ни разу ❌",
        "Давайте сливать {target}, он на мафии чисто коч устраивает!",
        "{target}, ты че голду на деф тратишь? Признавайся, кто ты!",
    ],
    "defense": [
        "Ребята, я чисто мирный, хисам халяль 100%! Не суетите!",
        "За что наезд? Я даже голду не забирал, вы че!",
        "Че за коч вы устроили? Где логика? Я мирный житель!",
        "Кто против меня голосует — тот мафия без пруфов!",
    ],
    "agreement": [
        "Факты говоришь, {target}! Поддерживаю, сливаем мафию.",
        "{target} чисто базы выдал, хисам халяль тема 🔥",
        "Согласен с {target}, тут всё предельно ясно.",
    ],
    "random_chat": [
        "Че за тишина? Кто тут мафия, признавайтесь за голду 😂",
        "Шериф, дай чек по халялю, кого проверял?",
        "Давайте без коча, просто сливаем самого тихаря.",
        "Реально, у кого какая роль? Напишите хоть в лс...",
    ],
}

# --- ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ---
lobby_active = False
lobby_timer = 0
lobby_chat_id = None
lobby_message_id = None
timer_thread = None
host_id = None
roles_menu_open = False  # Блокировка обновления экрана при настройке ролей

players = {}  # ID -> {name, is_ai, role, alive, will}
game_started = False
ai_bot_count = 0

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
      telebot.types.BotCommand("lobby", "⚔️ Обычное лобби (люди)"),
      telebot.types.BotCommand("ai_lobby", "🤖 Игра с умными ИИ-ботами"),
      telebot.types.BotCommand("help_roles", "📖 Описание 17 ролей"),
      telebot.types.BotCommand("roles", "📜 Список участников"),
      telebot.types.BotCommand("will", "✉️ Написать завещание"),
      telebot.types.BotCommand("stats", "👤 Мой профиль"),
      telebot.types.BotCommand("ping", "🟢 Проверка бота"),
  ]
  try:
    bot.set_my_commands(commands)
  except Exception:
    pass


def get_ai_setup_keyboard():
  markup = types.InlineKeyboardMarkup(row_width=4)
  btns = [
      types.InlineKeyboardButton(f"{i} ИИ", callback_data=f"set_ai_{i}")
      for i in range(1, 9)
  ]
  markup.add(*btns)
  markup.add(
      types.InlineKeyboardButton("⚙️ 12 ИИ-ботов", callback_data="set_ai_12"),
      types.InlineKeyboardButton("🔥 15 ИИ-ботов", callback_data="set_ai_15"),
  )
  return markup


def generate_ai_bots(count):
  global players
  used_names = random.sample(AI_NAMES, min(count, len(AI_NAMES)))

  for idx in range(count):
    bot_id = f"ai_bot_{idx+1}"
    bot_name = f"🤖 #{idx+1} {used_names[idx]}"
    players[bot_id] = {
        "name": bot_name,
        "is_ai": True,
        "role": None,
        "alive": True,
        "will": "Чисто по халялю играл...",
    }


def bot_respond_to_message(user_name, text, chat_id):
  if not game_started:
    return

  alive_bots = [p for p in players.values() if p.get("is_ai") and p["alive"]]
  alive_others = [
      p["name"] for p in players.values() if p["alive"] and p["name"] != user_name
  ]

  if not alive_bots:
    return

  responder = random.choice(alive_bots)
  if responder["name"] == user_name:
    return

  msg_lower = text.lower()
  target = (
      random.choice(alive_others) if alive_others else "кто-то из присутствующих"
  )

  if any(
      word in msg_lower
      for word in ["мафия", "шериф", "доктор", "кто", "где", "почему", "за что"]
  ):
    category = "suspicious"
  elif any(
      word in msg_lower for word in ["мирный", "халяль", "деф", "пруф", "голда"]
  ):
    category = "agreement"
  else:
    category = random.choice(["suspicious", "defense", "random_chat"])

  phrase_template = random.choice(SLANG_RESPONSES[category])
  reply_text = phrase_template.format(target=user_name)

  time.sleep(random.uniform(1.2, 2.5))
  try:
    bot.send_message(
        chat_id,
        f"💬 **{responder['name']}**: {reply_text}",
        parse_mode="Markdown",
    )
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

  # Если открыто меню настройки ролей, НЕ перерисовываем главное окно!
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
      f" `{len(players)}` (ИИ: {ai_bot_count})\n"
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


def start_game():
  global game_started, lobby_active, roles_menu_open
  total_roles = sum(selected_roles.values())

  if total_roles != len(players):
    bot.send_message(
        lobby_chat_id,
        f"❌ **Ошибка баланса!** Карт ролей ({total_roles}) != участников"
        f" ({len(players)}).",
        parse_mode="Markdown",
    )
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

    if not pdata.get("is_ai"):
      try:
        bot.send_message(
            uid,
            f"🎭 **ИГРА НАЧАЛАСЬ!**\n\nТвоя роль: **{role}**",
            parse_mode="Markdown",
        )
      except Exception:
        pass

  bot.send_message(
      lobby_chat_id,
      "🔥 **Игра началась!** Боты готовы к обсуждению!",
      parse_mode="Markdown",
  )


# --- ОБРАБОТЧИК СООБЩЕНИЙ ---


@bot.message_handler(
    func=lambda message: game_started and not message.text.startswith("/")
)
def handle_chat_discussion(message):
  threading.Thread(
      target=bot_respond_to_message,
      args=(message.from_user.first_name, message.text, message.chat.id),
  ).start()


# --- КОМАНДЫ ---


@bot.message_handler(commands=["ai_lobby"])
def cmd_ai_lobby(message):
  global lobby_active, lobby_timer, lobby_chat_id, lobby_message_id, players, host_id, selected_roles, game_started

  if game_started or lobby_active:
    bot.reply_to(message, "⚠️ Игра уже идёт!")
    return

  players = {message.from_user.id: {"name": message.from_user.first_name}}
  selected_roles = DEFAULT_ROLES.copy()
  host_id = message.from_user.id
  lobby_active = True
  lobby_timer = 300
  lobby_chat_id = message.chat.id

  bot.send_message(
      message.chat.id,
      "🤖 **РЕЖИМ С ИИ-БОТАМИ**\nВыберите сколько ботов добавить:",
      reply_markup=get_ai_setup_keyboard(),
  )


@bot.callback_query_handler(func=lambda call: call.data.startswith("set_ai_"))
def handle_ai_count(call):
  global ai_bot_count, lobby_message_id
  try:
    bot.answer_callback_query(call.id)
  except Exception:
    pass

  count = int(call.data.replace("set_ai_", ""))
  ai_bot_count = count

  generate_ai_bots(count)

  msg = bot.send_message(
      lobby_chat_id,
      "⏳ Создание ИИ-лобби...",
      parse_mode="Markdown",
      reply_markup=get_lobby_keyboard(),
  )
  lobby_message_id = msg.message_id
  update_lobby_message()


@bot.message_handler(commands=["lobby"])
def cmd_lobby(message):
  global lobby_active, lobby_timer, lobby_chat_id, lobby_message_id, players, host_id, selected_roles, game_started, ai_bot_count

  if game_started or lobby_active:
    bot.reply_to(message, "⚠️ Игра уже идет!")
    return

  players = {message.from_user.id: {"name": message.from_user.first_name}}
  selected_roles = DEFAULT_ROLES.copy()
  host_id = message.from_user.id
  ai_bot_count = 0
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


# --- ОБРАБОТЧИК КНОПОК С ЗАЩИТОЙ ОТ ЗАВИСАНИЯ ---


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
          call.id, "⚠️ Только хост настраивает роли!", show_alert=True
      )
      return
    roles_menu_open = True
    bot.edit_message_text(
        f"⚙️ **НАСТРОЙКА РОЛЕЙ** (Всего участников: {len(players)}):",
        lobby_chat_id,
        lobby_message_id,
        parse_mode="Markdown",
        reply_markup=get_roles_setup_keyboard(),
    )

  elif call.data.startswith("rp_"):
    r = call.data.replace("rp_", "")
    selected_roles[r] += 1
    bot.edit_message_reply_markup(
        lobby_chat_id, lobby_message_id, reply_markup=get_roles_setup_keyboard()
    )

  elif call.data.startswith("rm_"):
    r = call.data.replace("rm_", "")
    if selected_roles[r] > 0:
      selected_roles[r] -= 1
      bot.edit_message_reply_markup(
          lobby_chat_id,
          lobby_message_id,
          reply_markup=get_roles_setup_keyboard(),
      )

  elif call.data == "roles_done":
    roles_menu_open = False
    update_lobby_message()

  elif call.data == "force_start":
    start_game()


setup_bot_commands()
bot.infinity_polling()

import os
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
    
