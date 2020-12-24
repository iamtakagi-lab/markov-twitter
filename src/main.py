#!/usr/bin/env python3
# coding:utf-8

from twitter import Twitter
import exportModel
import urllib.parse
import os
import sys
import logging

from apscheduler.schedulers.background import BackgroundScheduler
sched = BackgroundScheduler()

class Config(object):
    SCHEDULER_API_ENABLED = True


logging.basicConfig(level=logging.DEBUG)

screen_name = os.environ["SCREEN_NAME"]

# Twitter API Keys
twitterKeys = {"CK": os.environ["TWITTER_API_CONKEY"],
               "CS": os.environ["TWITTER_API_CONSEC"],
               "AT": os.environ["TWITTER_API_ACCTOK"],
               "ATS": os.environ["TWITTER_API_ACCSEC"]
               }

# Twitter
twt = Twitter(
        screen_name, twitterKeys["CK"], twitterKeys["CS"], twitterKeys["AT"], twitterKeys["ATS"])

if __name__ == "__main__":
    sched.add_job(twt.tweet, 'cron', id='tweet', minute='*/30')
    sched.start()
    twt.stream()