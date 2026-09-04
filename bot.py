import random
import threading
import time
import telebot
from telebot import types

TOKEN = "8429089487:AAH_jKSvYpoPaD_RTqA6wSh5SynasROZtKo"
bot = telebot.TeleBot(TOKEN)

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
]

SLANG_RESPONSES = [
    "Мутный базар, {target}... Где пруфы, что ты мирный?",
    "{target} жестко суетит, это не хисам халяль ни разу ❌",
    "Ребята, я чисто мирный, хисам халяль 100%! Не суетите!",
    "Че за коч вы устроили? Где логика? Я мирный житель!",
    "Факты говоришь, {target}! Поддерживаю, сливаем мафию.",
    "Че за тишина? Кто тут мафия, признавайтесь за голду 😂",
]

lobby_active = False
game_started = False
lobby_timer = 120
lobby_chat_id = None
lobby_message_id = None
host_id = None
roles_menu_open = False

players = {}
selected_roles = {
    "Мафия": 1,
    "Доктор": 1,
    "Шериф": 1,
    "Мирный житель": 2,
}


def get_lobby_markup():
  markup = types.InlineKeyboardMarkup()
  markup.add(
      types.InlineKeyboardButton("⚔️ Войти", callback_data="join_game"),
      types.InlineKeyboardButton("🚪 Выйти", callback_data="leave_game"),
  )
  markup.add(
      types.InlineKeyboardButton(
          "⚙️ Настройка ролей", callback_data="setup_roles"
      )
  )
  markup.add(
      types.InlineKeyboardButton("🚀 Старт игры", callback_data="force_start")
  )
  return markup


def get_ai_markup():
  markup = types.InlineKeyboardMarkup(row_width=3)
  for i in range(1, 7):
    markup.add(
        types.InlineKeyboardButton(f"🤖 {i} ИИ", callback_data=f"set_ai_{i}")
    )
  return markup


def get_roles_markup():
  markup = types.InlineKeyboardMarkup(row_width=3)
  for role, count in selected_roles.items():
    markup.add(
        types.InlineKeyboardButton("➖", callback_data=f"rm_{role}"),
        types.InlineKeyboardButton(f"{role}: {count}", callback_data="noop"),
        types.InlineKeyboardButton("➕", callback_data=f"rp_{role}"),
    )
  total = sum(selected_roles.values())
  markup.add(
      types.InlineKeyboardButton(
          f"✅ Готово ({total} карт / {len(players)} игроков)",
          callback_data="roles_done",
      )
  )
  return markup


def update_lobby():
  global lobby_active, lobby_timer, lobby_chat_id, lobby_message_id, roles_menu_open
  if not lobby_active or not lobby_message_id or roles_menu_open:
    return

  players_list = (
      "\n".join([f"• `{p['name']}`" for p in players.values()])
      if players
      else "_Пока никто не вошел..._"
  )
  roles_summary = ", ".join(
      [f"{r}: {c}" for r, c in selected_roles.items() if c > 0]
  )
  mins, secs = lobby_timer // 60, lobby_timer % 60

  text = (
      "🏙 **МАФИЯ: ИГРОВОЕ ЛОББИ**\n"
      "───────────────────────\n"
      f"⏳ **До старта:** `{mins:02d}:{secs:02d}`\n"
      f"👥 **Игроков:** `{len(players)}`\n"
      f"⚙️ **Роли:** _{roles_summary}_\n\n"
      f"**Участники:**\n{players_list}"
  )

  try:
    bot.edit_message_text(
        text,
        lobby_chat_id,
        lobby_message_id,
        parse_mode="Markdown",
        reply_markup=get_lobby_markup(),
    )
  except Exception:
    pass


def timer_thread_func():
  global lobby_active, lobby_timer, game_started
  while lobby_active:
    time.sleep(5)
    if not lobby_active or game_started:
      break
    lobby_timer -= 5
    if lobby_timer <= 0:
      lobby_timer = 0
      update_lobby()
      start_game()
      break
    update_lobby()


def start_game():
  global game_started, lobby_active, roles_menu_open
  if game_started:
    return

  roles_menu_open = False
  total_roles = sum(selected_roles.values())

  if total_roles != len(players):
    if lobby_chat_id:
      bot.send_message(
          lobby_chat_id,
          f"❌ **Ошибка старта:** Количество ролей ({total_roles}) не совпадает с количеством игроков ({len(players)}).",
          parse_mode="Markdown",
      )
    return

  game_started = True
  lobby_active = False

  role_deck = []
  for role, count in selected_roles.items():
    role_deck.extend([role] * count)
  random.shuffle(role_deck)

  for (uid, p_data), role in zip(players.items(), role_deck):
    p_data["role"] = role
    p_data["alive"] = True
    if not p_data.get("is_ai"):
      try:
        bot.send_message(
            uid,
            f"🎭 **ИГРА НАЧАЛАСЬ!**\nВаша роль: **{role}**",
            parse_mode="Markdown",
        )
      except Exception:
        pass

  if lobby_chat_id:
    bot.send_message(
        lobby_chat_id,
        "🔥 **Игра успешно запущена!** Обсуждение в чате открыто.",
        parse_mode="Markdown",
    )


def ai_chatter(user_name, text, chat_id):
  if not game_started:
    return
  time.sleep(1.5)
  alive_bots = [p for p in players.values() if p.get("is_ai") and p["alive"]]
  if not alive_bots:
    return

  responder = random.choice(alive_bots)
  if responder["name"] == user_name:
    return

  reply = random.choice(SLANG_RESPONSES).format(target=user_name)
  bot.send_message(
      chat_id, f"💬 **{responder['name']}**: {reply}", parse_mode="Markdown"
  )


@bot.message_handler(commands=["start", "help"])
def cmd_start(help_message):
  help_text = (
      "🎮 **Добро пожаловать в игру Мафия!**\n\n"
      "**Доступные команды:**\n"
      "• /lobby — Создать стандартное лобби\n"
      "• /ai_lobby — Создать лобби с ИИ-ботами\n"
      "• /rules — Правила игры\n"
      "• /status — Статус текущей игры"
  )
  bot.send_message(help_message.chat.id, help_text, parse_mode="Markdown")


@bot.message_handler(commands=["rules"])
def cmd_rules(message):
  rules_text = (
      "📜 **ПРАВИЛА ИГРЫ МАФИЯ**\n\n"
      "1. **Мирные жители** должны вычислить и исключить всю мафию.\n"
      "2. **Мафия** каждую ночь выбирает жертву для устранения.\n"
      "3. **Доктор** может спасти одного игрока за ночь.\n"
      "4. **Шериф** проверяет игроков на принадлежность к мафии."
  )
  bot.send_message(message.chat.id, rules_text, parse_mode="Markdown")


@bot.message_handler(commands=["status"])
def cmd_status(message):
  if game_started:
    alive_count = sum(1 for p in players.values() if p["alive"])
    bot.send_message(
        message.chat.id,
        f"📊 **Статус игры:** Идет процесс игры.\n👥 Живых игроков: `{alive_count}`",
        parse_mode="Markdown",
    )
  elif lobby_active:
    bot.send_message(
        message.chat.id,
        "📊 **Статус игры:** Лобби открыто, идет набор игроков.",
        parse_mode="Markdown",
    )
  else:
    bot.send_message(
        message.chat.id,
        "📊 **Статус игры:** Игра не запущена. Используйте /lobby для создания.",
        parse_mode="Markdown",
    )


@bot.message_handler(
    func=lambda m: game_started and m.text and not m.text.startswith("/")
)
def chat_handler(message):
  threading.Thread(
      target=ai_chatter,
      args=(message.from_user.first_name, message.text, message.chat.id),
      daemon=True,
  ).start()


@bot.message_handler(commands=["lobby"])
def cmd_lobby(message):
  global lobby_active, lobby_timer, lobby_chat_id, lobby_message_id, players, host_id, game_started, roles_menu_open, selected_roles

  if game_started or lobby_active:
    bot.reply_to(message, "⚠️ Лобби уже создано и активно!")
    return

  players = {
      message.from_user.id: {
          "name": message.from_user.first_name,
          "is_ai": False,
          "alive": True,
      }
  }
  host_id = message.from_user.id
  selected_roles = {"Мафия": 1, "Доктор": 1, "Шериф": 1, "Мирный житель": 2}
  lobby_active = True
  game_started = False
  roles_menu_open = False
  lobby_timer = 120
  lobby_chat_id = message.chat.id

  msg = bot.send_message(
      lobby_chat_id, "⏳ Создание лобби...", reply_markup=get_lobby_markup()
  )
  lobby_message_id = msg.message_id
  update_lobby()

  threading.Thread(target=timer_thread_func, daemon=True).start()


@bot.message_handler(commands=["ai_lobby"])
def cmd_ai_lobby(message):
  global lobby_active, lobby_chat_id, players, host_id, game_started, roles_menu_open
  if game_started or lobby_active:
    bot.reply_to(message, "⚠️ Лобби уже создано и активно!")
    return

  players = {
      message.from_user.id: {
          "name": message.from_user.first_name,
          "is_ai": False,
          "alive": True,
      }
  }
  host_id = message.from_user.id
  lobby_active = True
  game_started = False
  roles_menu_open = False
  lobby_chat_id = message.chat.id

  bot.send_message(
      message.chat.id,
      "🤖 **Выберите количество ИИ-ботов для игры:**",
      reply_markup=get_ai_markup(),
  )


@bot.callback_query_handler(func=lambda c: c.data.startswith("set_ai_"))
def callback_ai_count(call):
  global lobby_message_id, selected_roles, lobby_timer
  bot.answer_callback_query(call.id)

  count = int(call.data.replace("set_ai_", ""))
  used_names = random.sample(AI_NAMES, min(count, len(AI_NAMES)))

  for i in range(count):
    bot_id = f"ai_{i}"
    players[bot_id] = {
        "name": f"🤖 {used_names[i]}",
        "is_ai": True,
        "alive": True,
    }

  selected_roles = {
      "Мафия": max(1, count // 3),
      "Доктор": 1,
      "Шериф": 1,
      "Мирный житель": len(players) - max(1, count // 3) - 2,
  }

  lobby_timer = 120
  msg = bot.send_message(
      lobby_chat_id,
      "⏳ Создаем лобби с ботами...",
      reply_markup=get_lobby_markup(),
  )
  lobby_message_id = msg.message_id
  update_lobby()

  threading.Thread(target=timer_thread_func, daemon=True).start()


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
  global lobby_active, players, game_started, roles_menu_open, selected_roles
  uid = call.from_user.id
  name = call.from_user.first_name
  bot.answer_callback_query(call.id)

  if not lobby_active or game_started:
    return

  if call.data == "join_game":
    if uid not in players:
      players[uid] = {"name": name, "is_ai": False, "alive": True}
      update_lobby()

  elif call.data == "leave_game":
    if uid in players and uid != host_id:
      del players[uid]
      update_lobby()

  elif call.data == "setup_roles":
    if uid != host_id:
      bot.answer_callback_query(
          call.id,
          "⚠️ Только создатель лобби может изменять настройки ролей!",
          show_alert=True,
      )
      return

    roles_menu_open = True
    bot.edit_message_text(
        "⚙️ **НАСТРОЙКА РОЛЕЙ В ИГРЕ:**",
        lobby_chat_id,
        lobby_message_id,
        parse_mode="Markdown",
        reply_markup=get_roles_markup(),
    )

  elif call.data.startswith("rp_"):
    if uid != host_id:
      return
    role = call.data.replace("rp_", "")
    selected_roles[role] += 1
    bot.edit_message_reply_markup(
        lobby_chat_id, lobby_message_id, reply_markup=get_roles_markup()
    )

  elif call.data.startswith("rm_"):
    if uid != host_id:
      return
    role = call.data.replace("rm_", "")
    if selected_roles[role] > 0:
      selected_roles[role] -= 1
      bot.edit_message_reply_markup(
          lobby_chat_id, lobby_message_id, reply_markup=get_roles_markup()
      )

  elif call.data == "roles_done":
    if uid != host_id:
      return
    roles_menu_open = False
    update_lobby()

  elif call.data == "force_start":
    if uid != host_id:
      bot.answer_callback_query(
          call.id,
          "⚠️ Только создатель может запустить игру досрочно!",
          show_alert=True,
      )
      return
    start_game()


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
    
