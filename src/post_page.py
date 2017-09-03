#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import time


def get_user_id_post_page(self, code):
    if self.login_status:
        log_string = 'Get user id on post page'
        self.log.debug(log_string)
        url = 'https://www.instagram.com/p/%s/?__a=1' % (code)
        try:
            r = self.s.get(url)
            all_data = json.loads(r.text)

            self.user_list = list(all_data['media']['likes']['nodes'])
            log_string = "User likes this post = %i" % (
                all_data['media']['likes']['count'])
            self.log.debug(log_string)
        except:
            self.media_on_feed = []
            self.log.debug("Except on get user list!!!!")
            time.sleep(10)
            return 0
    else:
        return 0
