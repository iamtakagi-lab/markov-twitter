#!/usr/bin/env python3
# coding:utf-8

import json
import time
from requests_oauthlib import OAuth1Session
import os
import markovify
import MeCab
import exportModel

from tweepy import OAuthHandler, Stream, StreamListener

# MeCab
mec = MeCab.Tagger("-d /usr/lib/mecab/dic/mecab-ipadic-neologd -O wakati")

class Twitter:
    oauth = None
    tweepy_oauth: OAuthHandler
    screen_name = None

    def __init__(self, screen_name, ck, cs, at=None, ats=None, callback=None):
        self.screen_name = screen_name
        self.oauth = OAuth1Session(ck, cs, at, ats, callback)
        self.tweepy_oauth = OAuthHandler(ck, cs)
        self.tweepy_oauth.set_access_token(at, ats)

    def requestToken(self):
        url = "https://api.twitter.com/oauth/request_token"
        return self.oauth.fetch_request_token(url)

    def getAuthenticateURL(self):
        url = "https://api.twitter.com/oauth/authenticate"
        self.requestToken()
        return self.oauth.authorization_url(url)

    def fetchTweets(self, params):
        url = "https://api.twitter.com/1.1/statuses/home_timeline.json"
        req = self.oauth.get(url, params=params)
        if req.status_code != 200:
            raise TwitterAPIError(req)
        return json.loads(req.text)

    def fetchTweetsLoop(self, params, loop):
        tweets = []
        params["count"] = 200
        params["include_rts"] = 1
        for i in range(loop):
            req = self.fetchTweets(params)
            if len(req) < 2:
                tweets.extend(req)
                break
            tweets.extend(req[:-1])
            params["max_id"] = req[-1]["id"]
        return tweets

    def postTweet(self, params):
        url = "https://api.twitter.com/1.1/statuses/update.json"

        req = self.oauth.post(url, params=params)
        if req.status_code != 200:
            raise TwitterAPIError(req)
        return json.loads(req.text)


    # TLからツイートを学習して呟きます (30分毎)
    def tweet(self):

        # TLから呟きを学習
        try:
            params = {}
            filepath = os.path.join("./chainfiles", "home_timeline.json")

            exportModel.generateAndExport(
                exportModel.loadTwitterAPI(self, params), filepath)
        except Exception as e:
            print(e)

        # 文書生成
        if not os.path.isfile("./chainfiles/home_timeline.json"):
            return print('Learned model file not found. まずはじめにツイートを学習させてください。')

        startWith = ""
        length = ""
        try:
            with open("./chainfiles/home_timeline.json") as f:
                textModel = markovify.Text.from_json(f.read())
                if startWith and 0 < len(startWith.strip()):
                    startWithStr = mec.parse(startWith).strip().split()
                    if textModel.state_size < len(startWithStr):
                        startWithStr = startWithStr[0:textModel.state_size]
                    startWithStr = " ".join(startWithStr)
                    try:
                        sentence = textModel.make_sentence_with_start(
                            startWithStr, tries=100)
                    except KeyError:
                        return print('生成失敗。該当開始語が存在しません。')

                elif str(length).isdecimal():
                    sentence = textModel.make_short_sentence(
                        int(length), tries=100)
                else:
                    sentence = textModel.make_sentence(tries=100)
                if sentence is not None:
                    sentence = "".join(sentence.split())

                    params = {
                        "status": sentence
                    }

                    # 呟く
                    self.postTweet(params)
                else:
                    print('生成失敗。複数回試してみてください。')
        except Exception as e:
            print(e)

# Tweepy

    def stream(self):
        l = StdOutListener()
        stream = Stream(self.tweepy_oauth, l)
        stream.filter(track=[f'@{self.screen_name}'])

class StdOutListener(StreamListener):
    """ A listener handles tweets that are received from the stream.
    This is a basic listener that just prints received tweets to stdout.
    """
    def reply(self, stauts):

        user_screen_name = stauts["user"]["screen_name"]

        # 自身のツイートには反応しない
        if user_screen_name == self.screen_name:
            return

        # 文書生成
        if not os.path.isfile("./chainfiles/home_timeline.json"):
            return print('Learned model file not found. まずはじめにツイートを学習させてください。')

        startWith = ""
        length = ""
        try:
            with open("./chainfiles/home_timeline.json") as f:
                textModel = markovify.Text.from_json(f.read())
                if startWith and 0 < len(startWith.strip()):
                    startWithStr = mec.parse(startWith).strip().split()
                    if textModel.state_size < len(startWithStr):
                        startWithStr = startWithStr[0:textModel.state_size]
                    startWithStr = " ".join(startWithStr)
                    try:
                        sentence = textModel.make_sentence_with_start(
                            startWithStr, tries=100)
                    except KeyError:
                        return print('生成失敗。該当開始語が存在しません。')
                elif str(length).isdecimal():
                    sentence = textModel.make_short_sentence(
                        int(length), tries=100)
                else:
                    sentence = textModel.make_sentence(tries=100)
                if sentence is not None:
                    sentence = "".join(sentence.split())

                params = {
                    "status": "@" + user_screen_name + ' ' + sentence,
                    "in_reply_to_status_id": stauts["id_str"],
                }

                # 返信
                self.postTweet(params)

        except Exception as e:
            print(e)

    def on_status(self, stauts):
        self.reply(stauts)
        return True

    def on_error(self, status):
        print(status)

# Error
class TwitterAPIError(Exception):
    def __init__(self, req):
        self.req = req

    def __str__(self):
        return str(self.req.status_code)