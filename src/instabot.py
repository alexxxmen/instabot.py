#!/usr/bin/env python
# -*- coding: utf-8 -*-

import urllib
import os
import atexit
import datetime
import itertools
import json
import logging
import random
import signal
import sys

if 'threading' in sys.modules:
    del sys.modules['threading']
import time
import requests
from unfollow_protocol import unfollow_protocol
from userinfo import UserInfo
from config import (LOG_TO, LOGGER, TELEGRAM_BOT_API_URL, TELEGRAM_BOT_TOKEN, ADMIN_TELEGRAM_IDS as telegram_ids)


if not os.path.exists(LOG_TO):
    os.mkdir(LOG_TO)


class Logger(object):
    def __init__(self, logger_name, file_handler):
        self._log = logging.getLogger(logger_name)
        self._log.addHandler(file_handler)
        self._log.setLevel(file_handler.level)

    def __getattr__(self, *args, **kwds):
        return getattr(self._log, *args, **kwds)


class InstaBot:
    """
    Instagram bot v 1.1.0
    like_per_day=1000 - How many likes set bot in one day.

    media_max_like=0 - Don't like media (photo or video) if it have more than
    media_max_like likes.

    media_min_like=0 - Don't like media (photo or video) if it have less than
    media_min_like likes.

    tag_list = ['cat', 'car', 'dog'] - Tag list to like.

    max_like_for_one_tag=5 - Like 1 to max_like_for_one_tag times by row.

    log_mod = 0 - Log mod: log_mod = 0 log to console, log_mod = 1 log to file,
    log_mod = 2 no log.

    https://github.com/LevPasha/instabot.py
    """

    url = 'https://www.instagram.com/'
    url_tag = 'https://www.instagram.com/explore/tags/%s/?__a=1'
    url_likes = 'https://www.instagram.com/web/likes/%s/like/'
    url_unlike = 'https://www.instagram.com/web/likes/%s/unlike/'
    url_comment = 'https://www.instagram.com/web/comments/%s/add/'
    url_follow = 'https://www.instagram.com/web/friendships/%s/follow/'
    url_unfollow = 'https://www.instagram.com/web/friendships/%s/unfollow/'
    url_login = 'https://www.instagram.com/accounts/login/ajax/'
    url_logout = 'https://www.instagram.com/accounts/logout/'
    url_media_detail = 'https://www.instagram.com/p/%s/?__a=1'
    url_user_detail = 'https://www.instagram.com/%s/?__a=1'

    user_agent = ("Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/48.0.2564.103 Safari/537.36")
    accept_language = 'ru-RU,ru;q=0.8,en-US;q=0.6,en;q=0.4'

    # If instagram ban you - query return 400 error.
    error_400 = 0
    # If you have 3 400 error in row - looks like you banned.
    error_400_to_ban = 3
    # If InstaBot think you are banned - going to sleep.
    ban_sleep_time = 2 * 60 * 60
    # max of error_400 for stop bot
    max_error_400 = 5

    # All counter.
    bot_mode = 0
    like_counter = 0
    follow_counter = 0
    unfollow_counter = 0
    comments_counter = 0
    current_user = 'hajka'
    current_index = 0
    current_id = 'abcds'
    # List of user_id, that bot follow
    bot_follow_list = []
    user_info_list = []
    user_list = []
    ex_user_list = []
    unwanted_username_list = []
    is_checked = False
    is_selebgram = False
    is_fake_account = False
    is_active_user = False
    is_following = False
    is_follower = False
    is_rejected = False
    is_self_checking = False
    is_by_tag = False
    is_follower_number = 0

    self_following = 0
    self_follower = 0

    # Other.
    user_id = 0
    media_by_tag = 0
    media_on_feed = []
    media_by_user = []
    login_status = False

    # For new_auto_mod
    run_auto_mod = True
    next_iteration = {"Like": 0, "Follow": 0, "Unfollow": 0, "Comments": 0}

    def __init__(self,
                 login,
                 password,
                 like_per_day=1000,
                 media_max_like=50,
                 media_min_like=0,
                 follow_per_day=0,
                 follow_time=5 * 60 * 60,
                 unfollow_per_day=0,
                 comment_list=[],
                 comments_per_day=0,
                 tag_list=[],
                 max_like_for_one_tag=5,
                 unfollow_break_min=15,
                 unfollow_break_max=30,
                 log_mod=0,
                 proxy="",
                 user_blacklist={},
                 tag_blacklist=[],
                 unwanted_username_list=[],
                 unfollow_whitelist=[]):

        # Log setting.
        fh = logging.FileHandler(os.path.join(LOG_TO, LOGGER.get('file') % login))
        fh.setLevel(LOGGER.get('level'))
        fh.setFormatter(LOGGER.get('formatter'))
        self.log = Logger('IBot', fh)

        self.bot_start = datetime.datetime.now()
        self.unfollow_break_min = unfollow_break_min
        self.unfollow_break_max = unfollow_break_max
        self.user_blacklist = user_blacklist
        self.tag_blacklist = tag_blacklist
        self.unfollow_whitelist = unfollow_whitelist
        self.comment_list = comment_list

        self.time_in_day = 24 * 60 * 60
        # Like
        self.like_per_day = like_per_day
        if self.like_per_day != 0:
            self.like_delay = self.time_in_day / self.like_per_day

        # Follow
        self.follow_time = follow_time
        self.follow_per_day = follow_per_day
        if self.follow_per_day != 0:
            self.follow_delay = self.time_in_day / self.follow_per_day

        # Unfollow
        self.unfollow_per_day = unfollow_per_day
        if self.unfollow_per_day != 0:
            self.unfollow_delay = self.time_in_day / self.unfollow_per_day

        # Comment
        self.comments_per_day = comments_per_day
        if self.comments_per_day != 0:
            self.comments_delay = self.time_in_day / self.comments_per_day

        # Don't like if media have more than n likes.
        self.media_max_like = media_max_like
        # Don't like if media have less than n likes.
        self.media_min_like = media_min_like
        # Auto mod seting:
        # Default list of tag.
        self.tag_list = tag_list
        # Get random tag, from tag_list, and like (1 to n) times.
        self.max_like_for_one_tag = max_like_for_one_tag
        # log_mod 0 to console, 1 to file
        self.log_mod = log_mod
        self.s = requests.Session()
        # if you need proxy make something like this:
        # self.s.proxies = {"https" : "http://proxyip:proxyport"}
        # by @ageorgios
        if proxy != "":
            proxies = {
                'http': 'http://' + proxy,
                'https': 'http://' + proxy,
            }
            self.s.proxies.update(proxies)
        # convert login to lower
        self.user_login = login.lower()
        self.user_password = password
        self.bot_mode = 0
        self.media_by_tag = []
        self.media_on_feed = []
        self.media_by_user = []
        self.unwanted_username_list = unwanted_username_list
        now_time = datetime.datetime.now()
        log_string = 'Instabot v1.1.0 started at %s:' % \
                     (now_time.strftime("%d.%m.%Y %H:%M"))
        self.log.debug(log_string)
        self.login()
        self.populate_user_blacklist()
        signal.signal(signal.SIGTERM, self.cleanup)
        atexit.register(self.cleanup)

    def populate_user_blacklist(self):
        for user in self.user_blacklist:
            user_id_url = self.url_user_detail % (user)
            info = self._send_get_request(user_id_url)

            # prevent error if 'Account of user was deleted or link is invalid
            from json import JSONDecodeError
            try:
                all_data = json.loads(info.text)
            except JSONDecodeError as e:
                self.log.debug('Account of user %s was deleted or link is '
                               'invalid' % (user))
            else:
                # prevent exception if user have no media
                id_user = all_data['user']['id']
                # Update the user_name with the user_id
                self.user_blacklist[user] = id_user
                log_string = "Blacklisted user %s added with ID: %s" % (user,
                                                                        id_user)
                self.log.debug(log_string)
                time.sleep(5 * random.random())

    def login(self):
        log_string = 'Trying to login as %s...\n' % (self.user_login)
        self.log.debug(log_string)
        self.s.cookies.update({
            'sessionid': '',
            'mid': '',
            'ig_pr': '1',
            'ig_vw': '1920',
            'csrftoken': '',
            's_network': '',
            'ds_user_id': ''
        })
        self.login_post = {
            'username': self.user_login,
            'password': self.user_password
        }
        self.s.headers.update({
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': self.accept_language,
            'Connection': 'keep-alive',
            'Content-Length': '0',
            'Host': 'www.instagram.com',
            'Origin': 'https://www.instagram.com',
            'Referer': 'https://www.instagram.com/',
            'User-Agent': self.user_agent,
            'X-Instagram-AJAX': '1',
            'X-Requested-With': 'XMLHttpRequest'
        })
        r = self._send_get_request(self.url)
        self.s.headers.update({'X-CSRFToken': r.cookies['csrftoken']})
        time.sleep(5 * random.random())
        login = self._send_post_request(
            self.url_login, data=self.login_post, allow_redirects=True)
        self.s.headers.update({'X-CSRFToken': login.cookies['csrftoken']})
        self.csrftoken = login.cookies['csrftoken']
        time.sleep(5 * random.random())

        if login.status_code != 200:
            self.log.warning('Login error! Connection error!')
            raise Exception("Login error! Connection error!")

        r = self._send_get_request('https://www.instagram.com/')
        finder = r.text.find(self.user_login)

        if finder == -1:
            self.login_status = False
            self.log.debug('Login error! Check your login data!')
            raise Exception("Login error! Check your login data!")

        ui = UserInfo()
        self.user_id = ui.get_user_id_by_login(self.user_login)
        self.login_status = True
        log_string = '%s login success!' % self.user_login
        self.log.debug(log_string)

    def logout(self):
        now_time = datetime.datetime.now()
        log_string = 'Logout: likes - %i, follow - %i, unfollow - %i, comments - %i.' % \
                     (self.like_counter, self.follow_counter,
                      self.unfollow_counter, self.comments_counter)
        self.log.info(log_string)
        work_time = now_time - self.bot_start
        log_string = 'Bot work time: %s' % (work_time)
        self.log.info(log_string)

        try:
            logout_post = {'csrfmiddlewaretoken': self.csrftoken}
            logout = self._send_post_request(self.url_logout, data=logout_post)
            self.log.info("Logout success!")
            self.login_status = False
        except:
            self.log.debug("Logout error!")

    def cleanup(self, *_):
        # Unfollow all bot follow
        if self.follow_counter >= self.unfollow_counter:
            for f in self.bot_follow_list:
                log_string = "Trying to unfollow: %s" % (f[0])
                self.log.debug(log_string)
                self.unfollow_on_cleanup(f[0])
                sleeptime = random.randint(self.unfollow_break_min,
                                           self.unfollow_break_max)
                log_string = "Pausing for %i seconds... %i of %i" % (
                    sleeptime, self.unfollow_counter, self.follow_counter)
                self.log.debug(log_string)
                time.sleep(sleeptime)
                self.bot_follow_list.remove(f)

        # Logout
        if (self.login_status):
            self.logout()
        exit(0)

    def get_media_id_by_tag(self, tag):
        """ Get media ID set, by your hashtag """

        if (self.login_status):
            log_string = "Get media id by tag: %s" % (tag)
            self.log.debug(log_string)
            if self.login_status == 1:
                url_tag = self.url_tag % (tag)
                try:
                    r = self._send_get_request(url_tag)
                    all_data = json.loads(r.text)

                    self.media_by_tag = list(all_data['tag']['media']['nodes'])
                except:
                    self.media_by_tag = []
                    self.log.debug("Except on get_media!")
            else:
                return 0

    def like_all_exist_media(self, media_size=-1, delay=True):
        """ Like all media ID that have self.media_by_tag """
        if not self.login_status:
            return

        if self.media_by_tag == 0:
            self.log.debug("No media to like!")
            return

        i = 0
        for d in self.media_by_tag:
            # Media count by this tag.
            if media_size > 0 or media_size < 0:
                media_size -= 1
                l_c = self.media_by_tag[i]['likes']['count']
                if ((l_c <= self.media_max_like and
                     l_c >= self.media_min_like) or
                    (self.media_max_like == 0 and
                     l_c >= self.media_min_like) or
                    (self.media_min_like == 0 and
                     l_c <= self.media_max_like) or
                    (self.media_min_like == 0 and
                     self.media_max_like == 0)):
                    for blacklisted_user_name, blacklisted_user_id in self.user_blacklist.items(
                    ):
                        if self.media_by_tag[i]['owner'][
                                'id'] == blacklisted_user_id:
                            self.log.debug(
                                "Not liking media owned by blacklisted user: "
                                + blacklisted_user_name)
                            return False
                    if self.media_by_tag[i]['owner'][
                            'id'] == self.user_id:
                        self.log.debug(
                            "Keep calm - It's your own media ;)")
                        return False

                    try:
                        caption = self.media_by_tag[i][
                            'caption'].encode(
                                'ascii', errors='ignore')
                        tag_blacklist = set(self.tag_blacklist)
                        if sys.version_info[0] == 3:
                            tags = {
                                str.lower(
                                    (tag.decode('ASCII')).strip('#'))
                                for tag in caption.split()
                                if (tag.decode('ASCII')
                                    ).startswith("#")
                            }
                        else:
                            tags = {
                                unicode.lower(
                                    (tag.decode('ASCII')).strip('#'))
                                for tag in caption.split()
                                if (tag.decode('ASCII')
                                    ).startswith("#")
                            }

                        if tags.intersection(tag_blacklist):
                            matching_tags = ', '.join(
                                tags.intersection(tag_blacklist))
                            self.log.debug(
                                "Not liking media with blacklisted tag(s): "
                                + matching_tags)
                            return False
                    except:
                        self.log.debug(
                            "Couldn't find caption - not liking")
                        return False

                    log_string = "Trying to like media: %s" % \
                                 (self.media_by_tag[i]['id'])
                    self.log.debug(log_string)
                    like = self.like(self.media_by_tag[i]['id'])

                    if like == 0:
                        return False

                    if like.status_code != 200:
                        log_string = "Not liked: %i" % like.status_code
                        self.log.debug(log_string)
                        return False

                    self.like_counter += 1
                    log_string = "Liked: %s. Like #%i." % (self.media_by_tag[i]['id'], self.like_counter)
                    self.log.debug(log_string)
                    i += 1

                    if not delay:
                        return True

                    time.sleep(self.like_delay * 0.9 + self.like_delay * 0.2 * random.random())

                else:
                    return False
            else:
                return False


    def like(self, media_id):
        """ Send http request to like media by ID """
        if self.login_status:
            url_likes = self.url_likes % (media_id)
            try:
                like = self._send_post_request(url_likes)
                last_liked_media_id = media_id
            except:
                self.log.debug("Except on like!")
                like = 0
            return like

    def unlike(self, media_id):
        """ Send http request to unlike media by ID """
        if self.login_status:
            url_unlike = self.url_unlike % (media_id)
            try:
                unlike = self._send_post_request(url_unlike)
            except:
                self.log.debug("Except on unlike!")
                unlike = 0
            return unlike

    def comment(self, media_id, comment_text):
        """ Send http request to comment """
        if self.login_status:
            comment_post = {'comment_text': comment_text}
            url_comment = self.url_comment % (media_id)
            try:
                comment = self._send_post_request(url_comment, data=comment_post)
                if comment.status_code == 200:
                    self.comments_counter += 1
                    log_string = 'Write: "%s". #%i.' % (comment_text,
                                                        self.comments_counter)
                    self.log.debug(log_string)
                return comment
            except:
                self.log.debug("Except on comment!")
        return False

    def follow(self, user_id):
        """ Send http request to follow """
        if self.login_status:
            url_follow = self.url_follow % (user_id)
            try:
                follow = self._send_post_request(url_follow)
                if follow.status_code == 200:
                    self.follow_counter += 1
                    log_string = "Followed: %s #%i." % (user_id,
                                                        self.follow_counter)
                    self.log.debug(log_string)
                return follow
            except:
                self.log.debug("Except on follow!")
        return False

    def unfollow(self, user_id):
        """ Send http request to unfollow """
        if self.login_status:
            url_unfollow = self.url_unfollow % (user_id)
            try:
                unfollow = self._send_post_request(url_unfollow)
                if unfollow.status_code == 200:
                    self.unfollow_counter += 1
                    log_string = "Unfollow: %s #%i." % (user_id,
                                                        self.unfollow_counter)
                    self.log.debug(log_string)
                return unfollow
            except:
                self.log.debug("Exept on unfollow!")
        return False

    def unfollow_on_cleanup(self, user_id):
        """ Unfollow on cleanup by @rjmayott """
        if self.login_status:
            url_unfollow = self.url_unfollow % (user_id)
            try:
                unfollow = self._send_post_request(url_unfollow)
                if unfollow.status_code == 200:
                    self.unfollow_counter += 1
                    log_string = "Unfollow: %s #%i of %i." % (
                        user_id, self.unfollow_counter, self.follow_counter)
                    self.log.debug(log_string)
                else:
                    log_string = "Slow Down - Pausing for 5 minutes so we don't get banned!"
                    self.log.debug(log_string)
                    time.sleep(300)
                    unfollow = self._send_post_request(url_unfollow)
                    if unfollow.status_code == 200:
                        self.unfollow_counter += 1
                        log_string = "Unfollow: %s #%i of %i." % (
                            user_id, self.unfollow_counter,
                            self.follow_counter)
                        self.log.debug(log_string)
                    else:
                        log_string = "Still no good :( Skipping and pausing for another 5 minutes"
                        self.log.debug(log_string)
                        time.sleep(300)
                    return False
                return unfollow
            except:
                log_string = "Except on unfollow... Looks like a network error"
                self.log.debug(log_string)
        return False

    def auto_mod(self):
        """ Star loop, that get media ID by your tag list, and like it """
        if self.login_status:
            while True:
                random.shuffle(self.tag_list)
                self.get_media_id_by_tag(random.choice(self.tag_list))
                self.like_all_exist_media(random.randint \
                                              (1, self.max_like_for_one_tag))

    def new_auto_mod(self):
        while self.run_auto_mod:
            # ------------------- Get media_id -------------------
            if len(self.media_by_tag) == 0:
                self.get_media_id_by_tag(random.choice(self.tag_list))
                self.this_tag_like_count = 0
                self.max_tag_like_count = random.randint(
                    1, self.max_like_for_one_tag)
            # ------------------- Like -------------------
            self.new_auto_mod_like()
            # ------------------- Follow -------------------
            self.new_auto_mod_follow()
            # ------------------- Unfollow -------------------
            self.new_auto_mod_unfollow()
            # ------------------- Comment -------------------
            self.new_auto_mod_comments()
            # Bot iteration in 3 sec
            time.sleep(3)
            # print("Tic!")

        msg = "IBot '%s' was stopped. " % self.user_login
        for t_id in telegram_ids:
            self._send_telegram_message(TELEGRAM_BOT_API_URL, TELEGRAM_BOT_TOKEN, t_id, msg)

        raise Exception("Something went wrong. IBot stopping...")

    def new_auto_mod_like(self):
        if time.time() > self.next_iteration["Like"] and self.like_per_day != 0 \
                and len(self.media_by_tag) > 0:
            # You have media_id to like:
            if self.like_all_exist_media(media_size=1, delay=False):
                # If like go to sleep:
                self.next_iteration["Like"] = time.time() + \
                                              self.add_time(self.like_delay)
                # Count this tag likes:
                self.this_tag_like_count += 1
                if self.this_tag_like_count >= self.max_tag_like_count:
                    self.media_by_tag = [0]
            # Del first media_id
            del self.media_by_tag[0]

    def new_auto_mod_follow(self):
        if time.time() > self.next_iteration["Follow"] and \
                        self.follow_per_day != 0 and len(self.media_by_tag) > 0:
            if self.media_by_tag[0]["owner"]["id"] == self.user_id:
                self.log.debug("Keep calm - It's your own profile ;)")
                return
            log_string = "Trying to follow: %s" % (
                self.media_by_tag[0]["owner"]["id"])
            self.log.debug(log_string)

            if self.follow(self.media_by_tag[0]["owner"]["id"]) != False:
                self.bot_follow_list.append(
                    [self.media_by_tag[0]["owner"]["id"], time.time()])
                self.next_iteration["Follow"] = time.time() + \
                                                self.add_time(self.follow_delay)

    def new_auto_mod_unfollow(self):
        if time.time() > self.next_iteration["Unfollow"] and \
                        self.unfollow_per_day != 0 and len(self.bot_follow_list) > 0:
            if self.bot_mode == 0:
                for f in self.bot_follow_list:
                    if time.time() > (f[1] + self.follow_time):
                        log_string = "Trying to unfollow #%i: " % (
                            self.unfollow_counter + 1)
                        self.log.debug(log_string)
                        self.auto_unfollow()
                        self.bot_follow_list.remove(f)
                        self.next_iteration["Unfollow"] = time.time() + \
                                                          self.add_time(self.unfollow_delay)
            if self.bot_mode == 1:
                unfollow_protocol(self)

    def new_auto_mod_comments(self):
        if time.time() > self.next_iteration["Comments"] and self.comments_per_day != 0 \
                and len(self.media_by_tag) > 0 \
                and self.check_exisiting_comment(self.media_by_tag[0]['code']) == False:
            comment_text = self.generate_comment()
            log_string = "Trying to comment: %s" % (self.media_by_tag[0]['id'])
            self.log.debug(log_string)
            if self.comment(self.media_by_tag[0]['id'], comment_text) != False:
                self.next_iteration["Comments"] = time.time() + \
                                                  self.add_time(self.comments_delay)

    def add_time(self, time):
        """ Make some random for next iteration"""
        return time * 0.9 + time * 0.2 * random.random()

    def generate_comment(self):
        c_list = list(itertools.product(*self.comment_list))

        repl = [("  ", " "), (" .", "."), (" !", "!")]
        res = " ".join(random.choice(c_list))
        for s, r in repl:
            res = res.replace(s, r)
        return res.capitalize()

    def check_exisiting_comment(self, media_code):
        url_check = self.url_media_detail % (media_code)
        try:
            check_comment = self._send_get_request(url_check)
            all_data = json.loads(check_comment.text)
        except Exception:
            self.log.exception("Error during parse check_exisiting_comment response")
            return True

        if all_data['graphql']['shortcode_media']['owner']['id'] == self.user_id:
                self.log.debug("Keep calm - It's your own media ;)")
                # Del media to don't loop on it
                del self.media_by_tag[0]
                return True
        comment_list = list(all_data['graphql']['shortcode_media']['edge_media_to_comment']['edges'])
        for d in comment_list:
            if d['node']['owner']['id'] == self.user_id:
                self.log.debug("Keep calm - Media already commented ;)")
                # Del media to don't loop on it
                del self.media_by_tag[0]
                return True
        return False

    def auto_unfollow(self):
        chooser = 1
        current_user = 'abcd'
        current_id = '12345'
        checking = True
        self.media_on_feed = []
        if len(self.media_on_feed) < 1:
            self.get_media_id_recent_feed()
        if len(self.media_on_feed) != 0:
            chooser = random.randint(0, len(self.media_on_feed) - 1)
            current_id = self.media_on_feed[chooser]['node']["owner"]["id"]
            current_user = self.media_on_feed[chooser]['node']["owner"][
                "username"]

            while checking:
                for wluser in self.unfollow_whitelist:
                    if wluser == current_user:
                        chooser = random.randint(0,
                                                 len(self.media_on_feed) - 1)
                        current_id = self.media_on_feed[chooser]['node'][
                            "owner"]["id"]
                        current_user = self.media_on_feed[chooser]['node'][
                            "owner"]["username"]
                        log_string = (
                            "found whitelist user, starting search again")
                        self.log.debug(log_string)
                        break
                else:
                    checking = False

        if self.login_status:
            now_time = datetime.datetime.now()
            log_string = "%s : Get user info %s" % (
                self.user_login, now_time.strftime("%d.%m.%Y %H:%M"))
            self.log.debug(log_string)
            if self.login_status == 1:
                url_tag = self.url_user_detail % (current_user)
                try:
                    r = self._send_get_request(url_tag)
                    all_data = json.loads(r.text)

                    self.user_info = all_data['user']
                    i = 0
                    log_string = "Checking user info.."
                    self.log.debug(log_string)

                    while i < 1:
                        follows = self.user_info['follows']['count']
                        follower = self.user_info['followed_by']['count']
                        media = self.user_info['media']['count']
                        follow_viewer = self.user_info['follows_viewer']
                        followed_by_viewer = self.user_info[
                            'followed_by_viewer']
                        requested_by_viewer = self.user_info[
                            'requested_by_viewer']
                        has_requested_viewer = self.user_info[
                            'has_requested_viewer']
                        log_string = "Follower : %i" % (follower)
                        self.log.debug(log_string)
                        log_string = "Following : %s" % (follows)
                        self.log.debug(log_string)
                        log_string = "Media : %i" % (media)
                        self.log.debug(log_string)
                        if follower / follows > 2:
                            self.is_selebgram = True
                            self.is_fake_account = False
                            self.log.debug('   >>>This is probably Selebgram account')
                        elif follows / follower > 2:
                            self.is_fake_account = True
                            self.is_selebgram = False
                            self.log.debug('   >>>This is probably Fake account')
                        else:
                            self.is_selebgram = False
                            self.is_fake_account = False
                            self.log.debug('   >>>This is a normal account')

                        if follows / media < 10 and follower / media < 10:
                            self.is_active_user = True
                            self.log.debug('   >>>This user is active')
                        else:
                            self.is_active_user = False
                            self.log.debug('   >>>This user is passive')

                        if follow_viewer or has_requested_viewer:
                            self.is_follower = True
                            self.log.debug("   >>>This account is following you")
                        else:
                            self.is_follower = False
                            self.log.debug('   >>>This account is NOT following you')

                        if followed_by_viewer or requested_by_viewer:
                            self.is_following = True
                            self.log.debug('   >>>You are following this account')

                        else:
                            self.is_following = False
                            self.log.debug('   >>>You are NOT following this account')
                        i += 1

                except:
                    self.log.exception("Error during get_info")
                    media_on_feed = []
                    time.sleep(20)
                    return 0
            else:
                return 0

            if self.is_selebgram is not False or self.is_fake_account is not False or self.is_active_user is not True or self.is_follower is not True:
                self.log.debug(current_user)
                self.unfollow(current_id)
                try:
                    del self.media_on_feed[chooser]
                except:
                    self.media_on_feed = []
            self.media_on_feed = []

    def get_media_id_recent_feed(self):
        if self.login_status:
            now_time = datetime.datetime.now()
            log_string = "%s : Get media id on recent feed" % (self.user_login)
            self.log.debug(log_string)
            if self.login_status == 1:
                url_tag = 'https://www.instagram.com/?__a=1'
                try:
                    r = self._send_get_request(url_tag)
                    all_data = json.loads(r.text)

                    self.media_on_feed = list(
                        all_data['graphql']['user']['edge_web_feed_timeline'][
                            'edges'])

                    log_string = "Media in recent feed = %i" % (
                        len(self.media_on_feed))
                    self.log.debug(log_string)
                except:
                    self.media_on_feed = []
                    self.log.debug("Except on get_media!")
                    time.sleep(20)
                    return 0
            else:
                return 0

    def _send_post_request(self, url,  data=None, allow_redirects=None, timeout=15):
        request = dict(timeout=timeout)
        if data:
            request['data'] = data

        if allow_redirects:
            request['allow_redirects'] = allow_redirects

        try:
            response = self.s.post(url, **request)

        except Exception:
            self.log.exception("Error during _send_post_request to '%s', data=%s" % (url, data))
            raise
        return self._check_response(response)

    def _send_get_request(self, url, timeout=15):
        try:
            response = self.s.get(url, timeout=timeout)
        except Exception:
            self.log.exception("Error during _send_get_request to '%s'" % url)
            raise
        return self._check_response(response)

    def _send_telegram_message(self, url, token, id, text):
        url = _make_url(url, token, id, text)
        response = requests.get(url)
        return response

    def _check_response(self, response):
        if response.status_code == 400:
            self.log.warning("Error. Response status code=%s." % response.status_code)
            self.error_400 += 1

            if self.error_400 >= self.max_error_400:
                self.log.warning("Max error 400 was received. Exit...")
                self._force_exit()

            if self.error_400 >= self.error_400_to_ban:
                # Look like you banned!
                self.log.warning("Attention '%s' response status_code 400" % self.error_400)
                self.log.warning("Going to sleep=%s" % self.ban_sleep_time)
                time.sleep(self.ban_sleep_time)

            raise Request400Exception("Error. Request status code=400, count=%s" % self.error_400)

        self.error_400 = 0
        return response

    def _force_exit(self):
        self.run_auto_mod = False
        exit(0)


def _make_url(url, token, id, text):
    return "%s%s/sendMessage?" % (url, token) + urllib.urlencode({'chat_id': id, 'text': str(text)})


class Request400Exception(Exception):
    pass
