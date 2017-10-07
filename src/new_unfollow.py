#!/usr/bin/env python
# -*- coding: utf-8 -*-


def new_unfollow(self, user_id, user_name):
    """ Send http request to unfollow """
    url_unfollow = self.url_unfollow % (user_id)
    try:
        unfollow = self._send_post_request(url_unfollow)
        if unfollow.status_code == 200:
            self.unfollow_counter += 1
            log_string = "Unfollow: %s #%i." % (user_name,
                                                self.unfollow_counter)
            self.log.debug(log_string)
        return unfollow
    except:
        self.log.debug("Exept on unfollow!")
        return False
