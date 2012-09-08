# coding: utf-8
#
#  Copyright (C) 2012 André Panisson
#  You can contact me by email (panisson@gmail.com) or write to:
#  Via Alassio 11/c - 10126 Torino - Italy
#
import tweepy
import datetime
import httplib
import logging
import time
import re
import hashlib
from mod_pywebsocket._stream_base import BadOperationException
import socket

logger = logging.getLogger("twitter")
logger.setLevel(logging.DEBUG)

def md5(s):
    m = hashlib.md5()
    m.update(s)
    return m.hexdigest()

class UnauthorizedException(Exception):
    
    def __init__(self, reason):
        self.reason = reason
        
    def __str__(self):
        return self.reason

class Status(object):
    __slots__ = ['status_id', 'text', 'from_user', 'name', 'count', 'profile_image_url']
    
    def __init__(self, status_id, text, from_user, name, count, profile_image_url):
        self.status_id = status_id
        self.text = text
        self.from_user = from_user
        self.name = name
        self.count = count
        self.profile_image_url = profile_image_url

class TwitterCollector(object):
    
    def __init__(self, consumer_key, consumer_secret, oauth_token, oauth_token_secret):
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.oauth_token = oauth_token
        self.oauth_token_secret = oauth_token_secret
        
        self.auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
        self.auth.set_access_token(oauth_token, oauth_token_secret)
        self.api = tweepy.API(self.auth)
        
    def remaining_hits(self):
        return self.api.rate_limit_status()['remaining_hits']
        
    def process_search(self, screen_names):
        step = 25
        nsteps = len(screen_names)/step
        
        for i in range(nsteps):
            
            result = []
            
            query_names = screen_names[i*step:i*step+step]
            if len(query_names) == 0:
                break
            
            query = " OR ".join(("from:%s"%f) for f in query_names)
            
            done = False
            while not done:
                try:
                    yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
                    result = self.api.search(q=query, rpp=100, result_type='mixed', since=yesterday.strftime('%Y-%m-%d'))
                    done = True
                except httplib.IncompleteRead, e:
                    logger.error(str(e), exc_info=True)
                    time.sleep(1)
                except tweepy.error.TweepError, e:
                    logger.error(str(e), exc_info=True)
                    if e.reason == "Invalid query":
                        logger.error('invalid query: %s', query)
                        break
                    time.sleep(1)
        
            for status in result:
                
                status_id = md5(status.text)
                text = status.text
                from_user = status.from_user
                name = status.from_user_name
                count = 1
                
                # Remove RTs from status text
                m = re.search('((?<=RT\s@)\w+)(:\s)(.*)', status.text)
                if m:
                    #source = m.group(1).lower()
                    #target = status.from_user
                    text = m.group(3)
                    status_id = md5(text)
                    from_user = m.group(1)
                    name = from_user
                    
                if 'recent_retweets' in status.metadata:
                    count = status.metadata['recent_retweets']
                    
                profile_image_url = status.profile_image_url
                
                yield Status(status_id, text, from_user, name, count, profile_image_url)
                
    def process_streaming(self, follow, status_handler):
        class StreamingListener(tweepy.StreamListener):
            
            def on_status(self, status):
                    
                if hasattr(status, 'retweeted_status'):
                    text = status.retweeted_status.text
                    status_id = md5(text)
                    from_user = status.retweeted_status.user.screen_name
                    name = status.retweeted_status.user.name
                    profile_image_url = status.retweeted_status.user.profile_image_url
                    count = 1
                    
                    s = Status(status_id, text, from_user, name, count, profile_image_url)
                    status_handler(s)
                    
                    logger.debug(status.retweeted_status.text)
        
        listener = StreamingListener()
        
        sleep_time = 1
        
        stream = tweepy.streaming.Stream(self.auth, listener, timeout=60.0)
        while (True):
            try:
                stream.filter(follow=follow)
            except IOError, e:
                # user disconnected
                logger.error('IOError, user disconnected: %s', str(e), exc_info=True)
                break;
            except BadOperationException:
                # user disconnected
                break;
            except socket.gaierror:
                logger.error('Stream closed', exc_info=True)
                # retry with exponential back off
                time.sleep(sleep_time)
                sleep_time *= 2
            
            except Exception, e:
                logger.error(str(e), exc_info=True)
                # retry with exponential back off
                time.sleep(sleep_time)
                sleep_time *= 2
                
        stream.disconnect()
        
    def friends_ids(self, user_id):
            try:
                return self.api.friends_ids(user_id=user_id)
            except tweepy.error.TweepError:
                print 'failed for user ', user_id
                raise UnauthorizedException('Unable to collect user network: Not authorized to access user %s.'%user_id)
            
    def get_screen_names(self, user_id_list):
        # max number of user_ids is 100
        for i in range(0, len(user_id_list), 100):
            users = self.api.lookup_users(user_ids=user_id_list[i:i+100])
            for twitter_user in users:
                yield twitter_user
        
