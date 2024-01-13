from ctypes import Union
from typing import Optional

from telegram import Message
from telegram.ext.filters import MessageFilter


class UserSecurityFilter(MessageFilter):

    def __init__(self, settings: dict):
        super().__init__()
        self._userlist = settings['users']

    def filter(self, message: Message) -> bool:
        if message.from_user.name in self._userlist:
            return True
        return False


class AdminSecurityFilter(MessageFilter):

    def __init__(self, settings: dict):
        super().__init__()
        self._userlist = settings['users']

    def filter(self, message: Message) -> bool:
        if message.from_user.name in self._userlist \
                and self._userlist[message.from_user.name] == 'admin':
            return True
        return False

