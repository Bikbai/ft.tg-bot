import re
import string
import sys
from argparse import ArgumentParser

from prettytable import PrettyTable
import logging
import collections
import traceback
from logging.handlers import RotatingFileHandler
from pydoc import html
from typing import Dict

import requests
import telegram
from telegram import ReplyKeyboardRemove, Update, InlineKeyboardButton, \
    InlineKeyboardMarkup, helpers, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo, Message
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackContext, \
    CallbackQueryHandler, ConversationHandler, DictPersistence

import src.tfs_utility as tfs_utility
from src.security import UserSecurityFilter, AdminSecurityFilter
from src.utility import *

sessionStore: Dict = {}
sessionStore.setdefault('-1', '-1')

# Enable logging

# проверяем рабочий каталог
if not os.path.exists(PROGRAM_DATA_PATH):
    os.mkdir(PROGRAM_DATA_PATH)

# проверяем каталог с логами
if not os.path.exists(f'{PROGRAM_DATA_PATH}/logs'):
    os.mkdir(f"{PROGRAM_DATA_PATH}/logs")


logging.basicConfig(
    format="%(asctime)s %(levelname)s %(module)s - %(funcName)20s %(message)s",
    level=logging.INFO,
    handlers=[RotatingFileHandler(f'{PROGRAM_DATA_PATH}/logs/bot_log.log', encoding='utf-8', maxBytes=100000, backupCount=10)],
)

# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

settings = load_config(logger)

tfs = tfs_utility.TfsManipulator(settings)

parser = ArgumentParser()
parser.add_argument("-tt", help="Токен телеграм-бота", required=True, metavar="BOT:TOKEN", dest="telegram_token")

args = parser.parse_args()

if settings.get('telegram_token', '') == '':
    logger.info('В настройках не сохранён токен бота, сохраняю')
    settings['telegram_token'] = args.telegram_token
    save_config(settings)

# хранилище последнего сообщения в разрезе chat_id. Храним, чтобы чистить клавиатуру сообщения
lastmessage = {}


async def clear_keyboards(chat_id):
    if lastmessage.get(chat_id, "") != "":
        message: Message = lastmessage.pop(chat_id)
        await message.edit_reply_markup(None)


def build_cancel_keyboard():
    btnCancel = KeyboardButton(text=FINISH_COMMAND)
    return ReplyKeyboardMarkup(keyboard=[[btnCancel]], resize_keyboard=True)


def build_help_keyboard(context: CallbackContext):
    btn1 = InlineKeyboardButton(text=f"Создать ошибку",
                                url=helpers.create_deep_linked_url(context.bot.username, BUG_COMMAND))
    btn2 = InlineKeyboardButton(text="Список ошибок", callback_data="query_wi")
    btn3 = InlineKeyboardButton(text="Помощь", callback_data="help_btn")
    return InlineKeyboardMarkup(inline_keyboard=[[btn1, btn2, btn3]])


async def query_wi_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    reply_str = tfs.query_wi()
    await query.answer()
    await update.effective_message.edit_reply_markup(None)
    await update.callback_query.message.reply_markdown(text=reply_str)
    return ConversationHandler.END


async def show_help_callback(update: Update, context: CallbackContext):
    await clear_keyboards(update.effective_chat.id)
    query = update.callback_query
    reply_str = 'Доступны функции:\n' \
                '*Создать ошибку*\n' \
                '- Перемещает в приватный чат с ботом, где в диалоге можно заполнить поля ошибки\n' \
                '*Список ошибок*\n' \
                '- Формирует список открытых ошибок, внесённых ранее.\n' \
                '*Помощь*\n' \
                '- Выдаёт данное сообщение.\n ' \
                'Также доступны команды /help и /list'
    await query.answer()
    await update.callback_query.message.reply_markdown(text=reply_str)
    return ConversationHandler.END


async def std_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # кнопка перемещает в приватный режим -> Web App только в привате
    await clear_keyboards(update.effective_chat.id)
    msg = await update.message.reply_markdown(
        text="Здрасти, я бот. Доступные возможности:",
        reply_markup=build_help_keyboard(context))
    lastmessage[update.effective_chat.id] = msg
    return HELP_STAGE


async def prompt_attach(update: Update):
    text = f'Теперь вы можете добавить приложения к ошибке просто послав файлы в чат, или нажать кнопку ' \
           f'{FINISH_COMMAND} для завершения\n' \
           f'Поддерживаются файлы текстовых форматов (т.н. документы) и картинки (т.н. фото)'

    await update.get_bot().send_message(
        chat_id=update.message.chat_id,
        text=text,
        reply_markup=build_cancel_keyboard())


# Handle incoming WebAppData
async def web_app_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info(f"Получены данные {update.effective_message.web_app_data.data}, chat_id = {update.message.chat_id}")
    chat_id = update.message.chat_id
    bot = update.get_bot()

    # Here we use `json.loads`, since the WebApp sends the data JSON serialized string
    data = json.loads(update.effective_message.web_app_data.data)
    sysinfo = f"Создано телеграм-ботом по заявке пользователя:\n" \
              f"username {update.effective_user.name}, \n" \
              f"fullname: {update.effective_user.full_name}"
    try:

        # функция возвращает идентификатор
        workitemId = tfs.create_wi(
            project_string=data["project"],
            title=data['title'],
            descr=data['descr'],
            request_number=data['request_number'],
            info=sysinfo)
        if workitemId == -1:
            logger.error(f"Ошибка создания workitem, chat_id = {update.message.chat_id}")
            text = "По непонятным причинам рабочий элемент создать не удалось, прерываем ввод."
            await bot.send_message(chat_id=chat_id, text=text, reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
    except Exception:
        logger.error(f"Ошибка создания workitem, chat_id = {update.message.chat_id}")
        reply_text = f'К сожалению, запрос выполнить невозможно \n' \
                     f'```{traceback.format_exc()[0:4000]}```'
        await update.message.reply_markdown(reply_text, reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    sessionStore.update({chat_id: workitemId})
    text = f'Создан дефект: {workitemId}'
    logger.info(text)
    # await update.message.reply_text(text, reply_markup=ReplyKeyboardRemove())
    await bot.send_message(chat_id=chat_id, text=text)
    await prompt_attach(update)
    return ATTACHMENT_ENTRY


# Define a `/bug` command handler.
async def bug_cmd_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_chat.type != "private":
        await std_reply(update, context)
        return HELP_STAGE

    logger.info(f"Получен запрос от {update.effective_user.name}, chat_id = {update.message.chat_id}")

    text = 'Команда для занесения новой ошибки или добавления к существующей вложения.\n' \
           'В первом случае - кнопка "Создать ошибку", вам будет выведена форма ввода свойств ошибки\n' \
           f'Во втором случае - кнопка "{ATTACH_COMMAND}", будет запрошен номер рабочего элемента (workitem) TFS.'

    btnBug = KeyboardButton(text="Создать ошибку", web_app=WebAppInfo(url=webAppUrl))
    btnAttach = KeyboardButton(text=ATTACH_COMMAND)
    btnCancel = KeyboardButton(text=FINISH_COMMAND)

    await update.message.reply_text(
        text=text,
        reply_markup=ReplyKeyboardMarkup(keyboard=[[btnBug, btnAttach, btnCancel]], resize_keyboard=True)
    )
    return STAGE1_HANDLER


async def list_cmd_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"Получен запрос от {update.effective_user.name}, chat_id = {update.message.chat_id}")
    await clear_keyboards(update.effective_chat.id)
    try:
        reply_text = tfs.query_wi()
    except Exception as err:
        reply_text = f'К сожалению, запрос выполнить невозможно \n' \
                     f'```{traceback.format_exc()[0:4000]}```'

    await update.message.reply_markdown(reply_text)
    return


async def attachment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if isinstance(update.message.effective_attachment, collections.abc.Sequence):
        file = await update.message.effective_attachment[-1].get_file()
    elif isinstance(update.message.effective_attachment, telegram.Document):
        file = await update.message.effective_attachment.get_file()
    else:
        await update.message.reply_text('Поддерживаются только фотографии и документы')
        return ATTACHMENT_ENTRY

    buf = bytearray()
    await file.download_as_bytearray(buf)

    f = await update.get_bot().get_file(file_id=file.file_id)
    filename = f.file_path.split('/')[-1]
    bug_id = sessionStore.get(update.message.chat_id)

    logger.info(f"file_path= {f.file_path}, size= {len(buf)}, bug_id = {bug_id}")

    if bug_id == -1:
        await update.message.reply_text('Аттач можно добавить, выбрав ошибку')
        return ATTACHMENT_ENTRY
    try:
        retcode = tfs.make_wi_attach(bug_id, buf, filename=f'{filename}')
        if retcode in (200, 201):
            text = f'Всё успешно.\nДля завершения нажмите "{FINISH_COMMAND}", либо добавьте еще картинок =)'
            await update.message.reply_text(text)
            logger.info(f"Успешно добавлен аттач к {bug_id}, chat_id = {update.message.chat_id}")
            return ATTACHMENT_ENTRY
        else:
            text = f'При вызове TFS API произошла ошибка, HTTP status code: {retcode}'
            logger.error(f'{text}, chat_id =  {update.message.chat_id}')
            await update.message.reply_text(text)
            return ConversationHandler.END
    except Exception:
        reply_text = f'К сожалению, запрос выполнить невозможно \n' \
                     f'```{traceback.format_exc()[0:4000]}```'
        await update.message.reply_markdown(reply_text, reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END


async def cancel_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # чистим сессию за собой
    logger.info(f"Завершение сессии: {update.effective_user.name}, chat_id = {update.message.chat_id}")
    sessionStore.pop(update.message.chat_id, None)
    await update.message.reply_text(text="Ввод завершен", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"Получен запрос от {update.effective_user.name}, chat_id = {update.message.chat_id}")
    text = 'С помощью бота вы можете создать ошибку и посмотреть уже имеющиеся\n' \
           'Команды для этого доступны в меню бота слева от поля вводат текста.\n' \
           'Также они дублированы командами /bug и /list'
    await update.message.reply_text(text, reply_markup=ReplyKeyboardRemove())
    return


async def test_deeplink_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bot = update.get_bot()
    uri = helpers.create_deep_linked_url(bot_username=bot.username, payload="43206")

    table = PrettyTable()
    table.field_names = ['Item', 'Price']
    table.add_row(['ham', '$3.99'])
    table.add_row(['egg', '$2.99'])
    table.add_row(['spam', 'Free!'])

    response = '```\n{}```'.format(table.get_string())
    await update.message.reply_text(response, parse_mode='Markdown')

    text_md = f'[43206]({uri})'
    await update.message.reply_markdown(text_md)
    return


async def add_attach_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info(f"Получен запрос от {update.effective_user.name}, chat_id = {update.message.chat_id}")
    text = 'Введите номер workitem, для которого добавляем вложения.'
    await update.message.reply_text(text, reply_markup=build_cancel_keyboard())
    return WI_NUMBER_ENTRY


async def wi_number_entry_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    workitemId = int(update.message.text)
    logger.info(f"Получен запрос от {update.effective_user.name}, chat_id = {update.message.chat_id}, wi: {workitemId}")
    if workitemId < 1:
        text = 'Номер это целое число больше единицы.'
        await update.message.reply_text(text, reply_markup=build_cancel_keyboard())
        return WI_NUMBER_ENTRY

    try:
        exists = tfs.check_wi_exists(workitemId)
    except Exception:
        reply_text = f'К сожалению, запрос выполнить невозможно \n' \
                     f'```{traceback.format_exc()[0:4000]}```'
        await update.message.reply_markdown(reply_text, reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    if exists:
        sessionStore.update({update.message.chat_id: workitemId})
        await prompt_attach(update)
        return ATTACHMENT_ENTRY
    text = 'Указанный номер рабочего элемента не найден или отсутствует.'
    await update.message.reply_text(text, reply_markup=build_cancel_keyboard())
    return WI_NUMBER_ENTRY


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    # Log the error before we do anything else, so we can see it even if something breaks.
    logger.error("Exception while handling an update:", exc_info=context.error)

    # traceback.format_exception returns the usual python message about an exception, but as a
    # list of strings rather than a single string, so we have to join them together.
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)

    # Build the message with some markup and additional information about what happened.
    # You might need to add some logic to deal with messages longer than the 4096 character limit.
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        "An exception was raised while handling an update\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
        "</pre>\n\n"
        f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
        f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )

    # Finally, send the message
    await context.bot.send_message(
        chat_id=2084106630, text=message, parse_mode=ParseMode.HTML
    )


async def send_to_webhook(tg_channel: str, tg_username: str, message: str, tg_name: str):
    channels = settings["track"]
    if tg_channel not in channels:
        logger.info(f"Проигнорировано сообщение из чата {tg_channel} ({tg_name})")
        return

    if channels.get(tg_channel, "") != "":
        thread = f"?thread_id={channels[tg_channel]}"
    else:
        thread = ""

    webhook_id = channels["webhook_id"]
    token = channels["webhook_token"]
    if webhook_id == "" or token == "":
        logger.error("Нет настроек форвардинга!")
        return

    url = f'https://discord.com/api/webhooks/{webhook_id}/{token}{thread}'

    data = {
        "username": tg_username,
        "content": message
    }

    requests.post(url, headers={"content-type": "application/json"}, json=data)
    logger.info(f"Сообщение из телеграм-канала {tg_name} перенаправлено в DC, id: {webhook_id}")


async def discord_redirect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_message.reply_to_message is not None:
        msg = f'> {update.effective_message.reply_to_message.text}\n\n {update.effective_message.text}'
    else:
        msg = f'{update.effective_message.text}'

    await send_to_webhook(
        tg_channel=str(update.effective_chat.id),
        tg_username=f"{update.effective_user.full_name}({update.effective_user.name})",
        message=msg,
        tg_name=update.effective_chat.title
    )


async def track_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_channel = str(update.effective_chat.id)
    command = []
    if update.message.text is not None:
        command = update.message.text.split()
    if len(command) != 2 or not str.isnumeric(command[1]):
        await update.message.reply_text("Формат команды /track <Числовой ид. канала в дискорде>")
        return
    settings["track"][tg_channel] = command[1]
    save_config(settings)
    await update.message.reply_text("Чат теперь успешно перенаправляется в ветку дискорда")


async def admin_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.effective_user.name
    if settings["users"][username] == 'user':
        return ConversationHandler.END
    btn1 = InlineKeyboardButton(text="Список", callback_data="admin_view")
    btn2 = InlineKeyboardButton(text="Добавить", callback_data="admin_add")
    button_markup = InlineKeyboardMarkup(inline_keyboard=[[btn1, btn2]])
    await update.message.reply_markdown(
        text="Доступные функции:",
        reply_markup=button_markup)
    return ADMIN_STAGE1


async def admin_view_callback(update: Update, context: CallbackContext):
    await update.callback_query.answer()
    table = PrettyTable()
    table.field_names = ['Имя', 'Админ']
    for key, value in settings["users"].items():
        table.add_row([key, value])
    response = '```\n{}```'.format(table.get_string())
    await update.effective_message.reply_markdown(response)
    return ConversationHandler.END


async def admin_add_callback(update: Update, context: CallbackContext):
    await update.callback_query.answer()
    reply_text = "Упомяните в сообщении @пользователей, которых нужно добавить в список. " \
                 "По завершении нажмите кнопку Завершить"
    await update.callback_query.message.reply_text(text=reply_text, reply_markup=build_cancel_keyboard())
    return ADMIN_STAGE2


async def admin_user_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message.text
    user_list = re.findall(r"@\S*", message)
    for value in user_list:
        if value in settings['users']:
            continue
        settings['users'][value] = 'user'
        save_config(settings)
        await update.effective_chat.send_message(text=f'Пользователь {value} успешно добавлен в список.')

    reply_text = "Упомяните в сообщении @пользователей, которых нужно добавить в список. " \
                 "По завершении нажмите кнопку Завершить"
    await update.effective_chat.send_message(text=reply_text, reply_markup=build_cancel_keyboard())
    return ADMIN_STAGE2


def main() -> None:
    """Start the bot."""
    react_regex = 'ошибк[а|у|и]|проблем[а|у|и]|дефект'

    persistence = DictPersistence(update_interval=1)  # (1)
    userFilter = UserSecurityFilter(settings)
    adminFilter = AdminSecurityFilter(settings)

    from warnings import filterwarnings
    from telegram.warnings import PTBUserWarning
    filterwarnings(action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)

    # Create the Application and pass it your bot's token.
    application = Application.builder() \
        .token(settings['telegram_token']) \
        .persistence(persistence) \
        .build()

    help_conversation = ConversationHandler(
        entry_points=[CommandHandler(command="help",
                                     callback=std_reply,
                                     filters=userFilter)],
        states={
            HELP_STAGE: [
                CommandHandler(command="help", callback=std_reply, filters=userFilter),
                # кнопка "Список"
                CallbackQueryHandler(callback=query_wi_callback, pattern='query_wi'),
                # кнопка "добавить"
                CallbackQueryHandler(callback=show_help_callback, pattern='help_btn'),
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_input_handler)],
    )

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("bug", bug_cmd_handler)],
        states={
            STAGE1_HANDLER: [
                MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler),
                MessageHandler(filters.Regex(f"^{ATTACH_COMMAND}$"), add_attach_handler),
                MessageHandler(filters.Regex(f"^{FINISH_COMMAND}$"), cancel_input_handler)
            ],
            WI_NUMBER_ENTRY: [
                MessageHandler(filters.Regex(f"^\\d+$"), wi_number_entry_handler),
                MessageHandler(filters.Regex(f"^{FINISH_COMMAND}$"), cancel_input_handler)
            ],
            ATTACHMENT_ENTRY: [
                MessageHandler(filters.Document.ALL | filters.PHOTO, attachment_handler),
                MessageHandler(filters.Regex(f"^{FINISH_COMMAND}$"), cancel_input_handler)
            ],
            HELP_STAGE: [
                CommandHandler(command="help", callback=std_reply, filters=userFilter),
                # кнопка "Список"
                CallbackQueryHandler(callback=query_wi_callback, pattern='query_wi'),
                # кнопка "добавить"
                CallbackQueryHandler(callback=show_help_callback, pattern='help_btn'),
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_input_handler)],
    )

    admin_handler = ConversationHandler(
        entry_points=[CommandHandler(command="admin",
                                     callback=admin_command_handler,
                                     filters=adminFilter)],
        states={
            ADMIN_STAGE1: [
                # кнопка "посмотреть"
                CallbackQueryHandler(callback=admin_view_callback, pattern='admin_view'),
                # кнопка "добавить"
                CallbackQueryHandler(callback=admin_add_callback, pattern='admin_add'),
            ],
            ADMIN_STAGE2: [
                MessageHandler(~filters.Regex(f"^{FINISH_COMMAND}$"), admin_user_input_handler),
                MessageHandler(filters.Regex(f"^{FINISH_COMMAND}$"), cancel_input_handler)]
        },
        fallbacks=[CommandHandler("cancel", cancel_input_handler)],
    )

    application.add_handler(conv_handler)
    application.add_handler(admin_handler)
    application.add_handler(help_conversation)

    application.add_handler(CommandHandler(
        command="list",
        callback=list_cmd_handler,
        filters=userFilter))

    application.add_handler(CommandHandler(
        command="help",
        callback=show_help_callback,
        filters=userFilter))

    application.add_handler(CommandHandler(
        command="start",
        callback=start_handler,
        filters=userFilter & filters.ChatType.PRIVATE))
    application.add_handler(CommandHandler(
        command="track",
        callback=track_handler,
        filters=adminFilter & ~filters.ChatType.PRIVATE))

    application.add_handler(MessageHandler(~filters.ChatType.PRIVATE, callback=discord_redirect))
    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

    application.add_error_handler(error_handler)
