# определения констант
import importlib.resources
import json
import os
import uuid
from json import JSONDecodeError
from logging import Logger

webAppUrl = "https://bikbai.github.io/TestWebApp/"
BUG_COMMAND = 'Make_defect'
FINISH_COMMAND = 'Завершить ввод'
ATTACH_COMMAND = 'Добавить вложений'
PROGRAM_DATA_PATH = f'{os.environ["programdata"]}/tfs_bot'
STAGE1_HANDLER, ATTACHMENT_ENTRY, WI_NUMBER_ENTRY, ADMIN_STAGE1, ADMIN_STAGE2, HELP_STAGE = range(6)


def __save_config(config: str):
    with open(f"{PROGRAM_DATA_PATH}/settings.json", "w") as file:
        file.write(config)


def save_config(config: dict):
    __save_config(json.dumps(config, ensure_ascii=False, indent=4))


def __make_std_config():
    config = importlib.resources.open_text(__package__, 'settings.json', encoding="CP1251").read()
    __save_config(config)
    return json.loads(config)


def load_config(logger: Logger) -> dict:
    config = {}
    # копируем стандартный конфиг, если файла нет
    if not os.path.exists(f"{PROGRAM_DATA_PATH}/settings.json"):
        logger.warning(f"Отсутствует файл настроек {PROGRAM_DATA_PATH}/settings.json, создаём стандартный")
        return __make_std_config()

    # читаем строку из файла и пытаемся разобрать
    with open(f"{PROGRAM_DATA_PATH}/settings.json", "r") as file:
        config_string = file.read()
    try:
        config = json.loads(config_string)
    except JSONDecodeError as e:
        logger.error(f"Ошибка чтения конфигурации, {e.args}")
        os.rename(f"{PROGRAM_DATA_PATH}/settings.json", f"{PROGRAM_DATA_PATH}/{uuid.uuid4()}.bad")
        config = __make_std_config()
    return config

