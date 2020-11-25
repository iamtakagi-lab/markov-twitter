#!/usr/bin/env python3
# coding:utf-8

from flask_apscheduler import APScheduler
from twitterTools import TwitterTools
import exportModel
import MeCab
import urllib.parse
import os
import sys

from flask import Flask, request, redirect, abort, jsonify

from flask_apscheduler import APScheduler

class Config(object):
    SCHEDULER_API_ENABLED = True


scheduler = APScheduler()

app = Flask(__name__)

import datetime

import markovify

import logging
logging.basicConfig(level=logging.DEBUG)

# Tweet Source
source = os.environ["SOURCE"]

# Twitter API Keys
twitterKeys = {"CK": os.environ["TWITTER_API_CONKEY"],
               "CS": os.environ["TWITTER_API_CONSEC"],
               "AT": os.environ["TWITTER_API_ACCTOK"],
               "ATS": os.environ["TWITTER_API_ACCSEC"]
               }

# MeCab
mec = MeCab.Tagger("-d /usr/lib/mecab/dic/mecab-ipadic-neologd -O wakati")

# TLからツイートを学習して呟きます
@scheduler.task('interval', id='tweet', minutes=15, misfire_grace_time=900)
def tweet():
    global twitterKeys
    twt = TwitterTools(
        twitterKeys["CK"], twitterKeys["CS"], twitterKeys["AT"], twitterKeys["ATS"])

    # 1. TLから呟きを学習
    try:
        params = {}
        filepath = os.path.join("./chainfiles", "home_timeline.json")

        exportModel.generateAndExport(
            exportModel.loadTwitterAPI(twt, params), filepath)
    except Exception as e:
        print(e)

    # 2. 文書生成
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
                    "status": sentence,
                    "source": source
                }

                # 3. 呟く
                twt.postTweet(params)
            else:
                print('生成失敗。複数回試してみてください。')
    except Exception as e:
        print(e)


if __name__ == "__main__":
    port = 5000
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    scheduler.init_app(app)
    scheduler.start()
    app.run(host = "0.0.0.0", port = port)