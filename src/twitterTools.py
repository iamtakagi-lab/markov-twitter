#!/usr/bin/env python3
# coding:utf-8

import json
import threading
import time
from requests_oauthlib import OAuth1Session
from concurrent.futures import thread


class TwitterTools:
    oauth = None
    last_time = 0
    re_t_network = 16
    re_t_http = 5
    re_t_420 = 60

    def __init__(self, ck, cs, at=None, ats=None, callback=None):
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

    def __reset_backoff_time(self):
        self.re_t_network = 16
        self.re_t_http = 5
        self.re_t_420 = 60

    def __streaming_thread(self, request, func):
        self.last_time = time.time()
        for line in request.iter_lines(decode_unicode=True):

            self.last_time = time.time()
            if line:
                # 取得したJsonデータ(バイト列)を辞書形式に変換
                func(json.loads(line))

    def startStreaming(self, params, func):
        while True:
            try:
                # リクエストを送る
                req = self.oauth.post('https://stream.twitter.com/1.1/statuses/filter.json',
                            params = params,
                            stream = True)

                req.encoding = 'utf-8'

                # リクエストのステータスコードを確認
                if req.status_code == 200:
                    self.__reset_backoff_time()

                    thread = threading.Thread(target=self.__streaming_thread,args=([req,func]))
                    thread.setDaemon(True)
                    thread.start()

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
                    print(f'420 : Rate Limited. Recconecting... wait {self.re_t_420}s')
                    time.sleep(self.re_t_http)
                    self.re_t_http *= 2
                elif req.status_code == 503:
                    # 再接続が必要なHTTPエラーの場合、待機時間を2倍に伸ばす(最大320秒)
                    print(f'503 : Service Unavailable. Reconnecting... wait {self.re_t_http}s')
                    time.sleep(self.re_t_http)
                    self.re_t_http *= 2
                    if self.re_t_http > 320:
                        raise TwitterAPIError('503 : Service Unavailable.')

                else:
                    raise TwitterAPIError(f'HTTP ERRORE : {req.status_code}')

            except KeyboardInterrupt: # Ctrl + C で強制終了できる
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