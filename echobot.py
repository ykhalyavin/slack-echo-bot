import os
import sys
import time

from slackclient import SlackClient


class Bot:
    def __init__(self, token):
        self.client = SlackClient(token)
        self.im_ids = []
        self.last_ping = time.time()

    def start(self):
        self.client.rtm_connect()
        self.im_ids = self.get_im_ids()

        while True:
            for r in self.client.rtm_read():
                if 'type' not in r:
                    pass
                elif r['type'] == 'message':
                    self.process_message(r)
                elif r['type'] == 'im_created':
                    self.im_ids = self.get_im_ids()

            self.ping()
            time.sleep(0.2)

    def process_message(self, r):
        if 'subtype' in r or 'reply_to' in r:
            return
        if r['channel'] in self.im_ids or self.is_bot_mentioned(r['text']):
            self.client.rtm_send_message(r['channel'], r['text'])

    def is_bot_mentioned(self, msg):
        bot_id = self.client.server.login_data['self']['id']
        bot_mentioned = '<@{}>'.format(bot_id)

        return bot_mentioned in msg

    def get_im_ids(self):
        return [x['id'] for x in self.client.api_call('im.list')['ims']]

    def ping(self):
        now = int(time.time())
        if now > self.last_ping + 3:
            self.client.server.ping()
            self.last_ping = now


bot = Bot(os.environ['SLACKBOT_TOKEN'])


try:
    bot.start()
except KeyboardInterrupt:
    sys.exit(0)
