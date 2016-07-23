import json
import os
import sys

import aiohttp
import asyncio


class Bot:
    def __init__(self, token, channel):
        self.get = channel.get
        self.put = channel.put
        self.token = token
        self.ws = None
        self.bot_id = None
        self.im_ids = []

    async def api_call(self, method, data=None):
        async with aiohttp.ClientSession() as session:
            form = aiohttp.FormData(data or {})
            form.add_field('token', self.token)
            async with session.post('https://slack.com/api/{0}'.format(method),
                                    data=form) as response:
                assert 200 == response.status, ('{0} with {1} failed.'
                                                .format(method, data))

                return await response.json()

    async def ping(self):
        assert self.ws is not None, 'Websocket must be opened first'

        while True:
            self.ws.send_str(json.dumps({'type': 'ping'}))
            await asyncio.sleep(5)

    async def message_processor(self):
        while True:
            data = await self.get()
            m = {
                'type': 'message',
                'channel': data['channel'],
                'text': data['text']
            }

            self.ws.send_str(json.dumps(m))

    async def start(self):
        ret = await self.api_call('rtm.start')
        assert ret['ok'], 'Error connecting to RTM'

        self.bot_id = ret['self']['id']

        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(ret['url']) as ws:
                self.ws = ws
                self.im_ids = await self.get_im_ids()

                # Slack requires to send us ping every several second of
                # inactivity
                asyncio.ensure_future(self.ping())
                # Appropriate messages will be processed in this future using
                # asyncio.Queue get channel
                asyncio.ensure_future(self.message_processor())

                async for msg in ws:
                    assert msg.tp == aiohttp.MsgType.text
                    await self.process_rtm_response(json.loads(msg.data))

    async def process_rtm_response(self, data):
        if 'type' not in data:
            return

        elif data['type'] == 'message':
            await self.process_message(data)
        elif data['type'] == 'im_created':
            self.im_ids = await self.get_im_ids()

    async def get_im_ids(self):
        ret = await self.api_call('im.list')

        return [x['id'] for x in ret['ims']]

    async def process_message(self, data):
        if 'subtype' in data or 'reply_to' in data:
            return

        # Response only to a private channnel message or mention (e.g. @bot) in
        # common channels
        if (data['channel'] in self.im_ids or
                self.is_bot_mentioned(data['text'])):
            await self.put(data)

    def is_bot_mentioned(self, msg):
        return '<@{}>'.format(self.bot_id) in msg


# Use channel to ensure messages processing order
channel = asyncio.Queue()
bot = Bot(os.environ['SLACKBOT_TOKEN'], channel)

try:
    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    loop.run_until_complete(bot.start())
except KeyboardInterrupt:
    sys.exit(0)
finally:
    loop.close()
