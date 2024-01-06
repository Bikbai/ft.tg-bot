import asyncio
import textwrap

import aiohttp
import nextcord as nextcord
import requests

token = "r1_FA_hLN6h675sMzqXjwCcCEj99akXSpG4uj9fwkxAoKsaQaMrAuH-AkklbwclaQbZt"
webhook_id = '1192949189626318960'
base_uri = 'https://discord.com/api/webhooks/'

url = f'{base_uri}/{webhook_id}/{token}'
url = 'https://discord.com/api/webhooks/1192949189626318960/r1_FA_hLN6h675sMzqXjwCcCEj99akXSpG4uj9fwkxAoKsaQaMrAuH-AkklbwclaQbZt'

headers = {
    "content-type": "application/json"
}

data = {
  "username": "Telegram bot",
  "content": "Hello, World!",
  "embeds": [{
    "title": "Hello, Embed!",
    "description": "This is an embedded message."
  }]
}

res = requests.post(url, headers=headers, json=data)




async def send_to_webhook(message, username):
    session = aiohttp.ClientSession()
    print('Sending w/o media')
    webhook = nextcord.Webhook.from_url(url, session=session)
    for line in textwrap.wrap(message, 2000, replace_whitespace=False):
        x = await webhook.send(content=line, username=username)


#asyncio.get_event_loop().run_until_complete(send_to_webhook("aaa", "bbb"))

