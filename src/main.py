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

import datetime

import markovify

import logging

class Config(object):
    SCHEDULER_API_ENABLED = True


scheduler = APScheduler()

app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG)

screen_name = os.environ["SCREEN_NAME"]

# Twitter API Keys
twitterKeys = {"CK": os.environ["TWITTER_API_CONKEY"],
               "CS": os.environ["TWITTER_API_CONSEC"],
               "AT": os.environ["TWITTER_API_ACCTOK"],
               "ATS": os.environ["TWITTER_API_ACCSEC"]
               }

# MeCab
mec = MeCab.Tagger("-d /usr/lib/mecab/dic/mecab-ipadic-neologd -O wakati")

# Twitter
twt = TwitterTools(
        twitterKeys["CK"], twitterKeys["CS"], twitterKeys["AT"], twitterKeys["ATS"])

@app.route('/')
def index():
    return "Markov Twitter"


def reply(status):
    global screen_name, twt

    user_screen_name = status["user"]["screen_name"]

    # 自身のツイートには反応しない
    if user_screen_name == screen_name: return

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
            twt.postTweet(params)

    except Exception as e:
        print(e)


# TLからツイートを学習して呟きます (30分おき)
scheduler.task('cron', id='tweet', minute='*/30')
# @scheduler.task('interval', id='tweet', seconds=30, misfire_grace_time=900) # DEBUG
def tweet():
    global twt

    # TLから呟きを学習
    try:
        params = {}
        filepath = os.path.join("./chainfiles", "home_timeline.json")

        exportModel.generateAndExport(
            exportModel.loadTwitterAPI(twt, params), filepath)
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
                twt.postTweet(params)
            else:
                print('生成失敗。複数回試してみてください。')
    except Exception as e:
        print(e)


if __name__ == "__main__":

    # Tweet Scheduler
    scheduler.init_app(app)
    scheduler.start()

    # Stremaming
    twt.startStreaming({'track':'@' + screen_name}, reply)

    # Start
    app.run(host = os.getenv('HOST', '0.0.0.0'), port = int(os.getenv('PORT', '5000')))