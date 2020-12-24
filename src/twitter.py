#!/usr/bin/env python3
# coding:utf-8

import json
import threading
import schedule
import time
from requests_oauthlib import OAuth1Session
import os
import markovify
import MeCab
import exportModel

# MeCab
mec = MeCab.Tagger("-d /usr/lib/mecab/dic/mecab-ipadic-neologd -O wakati")


class Twitter:
    oauth = None

    screen_name = None

    last_time = 0
    re_t_network = 16
    re_t_http = 5
    re_t_420 = 60

    def __init__(self, screen_name, ck, cs, at=None, ats=None, callback=None):
        self.screen_name = screen_name
        self.oauth = OAuth1Session(ck, cs, at, ats, callback)

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

    def reply(self, status):

        user_screen_name = status["user"]["screen_name"]

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
                    "status": "@" + user_screen_name + " " + sentence,
                    "in_reply_to_status_id": status["id_str"],
                }

                # 返信
                self.postTweet(params)

        except Exception as e:
            print(e)

    def __reset_backoff_time(self):
        self.re_t_network = 16
        self.re_t_http = 5
        self.re_t_420 = 60

    def stream(self):
        params = {'track': '@' + self.screen_name}

        while True:
            try:
                # リクエストを送る
                req = self.oauth.post('https://stream.twitter.com/1.1/statuses/filter.json',
                                      params=params,
                                      stream=True)

                req.encoding = 'utf-8'

                # リクエストのステータスコードを確認
                if req.status_code == 200:
                    self.__reset_backoff_time()

                    # 関数呼び出し
                    for line in req.iter_lines(decode_unicode=True):
                        self.last_time = time.time()
                        if line:
                            # 取得したJsonデータ(バイト列)を辞書形式に変換
                            self.reply(json.loads(line))

                    # 90秒間受信データがない場合、whileを抜け再接続
                    while time.time() - self.last_time < 90:
                        time.sleep(90 - (time.time() - self.last_time))

                elif req.status_code == 401:
                    raise TwitterAPIError('404 : Unauthorized')
                elif req.status_code == 403:
                    raise TwitterAPIError('403 : Forbidden')
                elif req.status_code == 406:
                    raise TwitterAPIError('406 : Not Acceptable')
                elif req.status_code == 413:
                    raise TwitterAPIError('413 : Too Long')
                elif req.status_code == 416:
                    raise TwitterAPIError('416 : Range Unacceptable')
                elif req.status_code == 420:
                    # 420エラーの場合、待機時間を2倍に伸ばす(制限なし)
                    print(
                        f'420 : Rate Limited. Recconecting... wait {self.re_t_420}s')
                    time.sleep(self.re_t_http)
                    self.re_t_http *= 2
                elif req.status_code == 503:
                    # 再接続が必要なHTTPエラーの場合、待機時間を2倍に伸ばす(最大320秒)
                    print(
                        f'503 : Service Unavailable. Reconnecting... wait {self.re_t_http}s')
                    time.sleep(self.re_t_http)
                    self.re_t_http *= 2
                    if self.re_t_http > 320:
                        raise TwitterAPIError('503 : Service Unavailable.')

                else:
                    raise TwitterAPIError(f'HTTP ERRORE : {req.status_code}')

            except KeyboardInterrupt:  # Ctrl + C で強制終了できる
                break
            except ConnectionError:
                time.sleep(self.re_t_network)
                self.re_t_network += 16
                if self.re_t_network > 250:
                    raise TwitterAPIError('Network Error')
            except:
                raise

class TwitterAPIError(Exception):
    def __init__(self, req):
        self.req = req

    def __str__(self):
        return str(self.req.status_code)