import logging
import re
import sys
from logging.handlers import RotatingFileHandler

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(module)s - %(funcName)20s %(message)s",
    level=logging.INFO,
    handlers=[RotatingFileHandler(f'text.log', encoding='utf-8', maxBytes=100000, backupCount=10)],
)

# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


logger.warning(
    'Сообщение из телеграм-канала ТЕСТ 👁 перенаправлено в DC, id: 1192949189626318960')