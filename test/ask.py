import requests
import logging

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(module)s - %(funcName)20s %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

settings = {
    "forwarding": {
        "webhook_id": "1192949189626318960",
        "webhook_token": "r1_FA_hLN6h675sMzqXjwCcCEj99akXSpG4uj9fwkxAoKsaQaMrAuH-AkklbwclaQbZt",
        "ФЦОД": "1193214515010084946",
        "ТЕСТ": ""
    }
}

def send_to_webhook(tg_channel, tg_username, message):
    channels = settings["forwarding"]
    if tg_channel not in channels:
        logger.info(f"Проигнорировано сообщение из чата {tg_channel}")
        return

    if channels[tg_channel] != "":
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
        "username": "Telegram bot",
        "content": f"В телеграм-канале {tg_channel} пользователем {tg_username} размещено сообщение:",
        "embeds": [{
            "description": f"{message}"
        }]
    }

    requests.post(url, headers={"content-type": "application/json"}, json=data)
    logger.info(f"Сообщение из чата {tg_channel} перенаправлено в DS")


send_to_webhook("ТЕСТ", "Пользователь", "Сообщение")