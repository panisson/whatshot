# coding: utf-8
#
#  Copyright (C) 2012 André Panisson
#  You can contact me by email (panisson@gmail.com) or write to:
#  Via Alassio 11/c - 10126 Torino - Italy
#

import re
import hashlib
import operator
import simplejson
import sys
from nltk.stem.wordnet import WordNetLemmatizer
import string
import ttp
from whatshot.model import User, Followers, commit
import logging
from whatshot import config
from websockets.twitter import TwitterCollector, UnauthorizedException

logger = logging.getLogger("core")
logger.setLevel(logging.DEBUG)

#FIXME: this is not a good way to change the default encoding
reload(sys)
sys.setdefaultencoding('utf-8')

# setup word lemmatization
stop_words = set(eval(file(config.STOPWORDS_FILE).read().replace("\n", "")))
lmtzr = WordNetLemmatizer()

# setup the tweet parsers
UTF_CHARS = ur'a-z0-9_\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u00ff'
TAG_EXP = ur'(^|[^0-9A-Z&/]+)(#|\uff03)([0-9A-Z_]*[A-Z_]+[%s]*)' % UTF_CHARS
TAG_REGEX = re.compile(TAG_EXP, re.UNICODE | re.IGNORECASE)
tweet_parser = ttp.Parser()

def md5(s):
    m = hashlib.md5()
    m.update(s)
    return m.hexdigest()

class WebsocketProcessor(object):
    '''
    Creates a request processor.
    The request is supposed to be a websockets request.
    '''
    def __init__(self, request):
        self.request = request
        
    def send_message(self, msg):
        self.request.ws_stream.send_message(msg, binary=False)


class Processor(WebsocketProcessor):
    '''
    Creates a WebsocketProcessor for the whatshot application.
    '''
    
    def __init__(self, request):
        WebsocketProcessor.__init__(self, request)
        
        self.hashtags = {}
        self.htref = {}
        self.sent_tweets = set()
        self.hashtag_tweets = {}
        self.status_count = {}
        
    def process_user(self, screen_name):
        '''
        This is our core function.
        First, we collect the second-level user network.
        After, we rank the users in the network and get the top n.
        We make an initial search for recent status posted by these users,
        and lastly we connect to the Twitter Streaming API to get real-time statuses.
        '''
        
        # get the user data
        user = User.select_by_screen_name(screen_name)
        
        if not user:
            logger.error('User not found')
            self.sent_to_user('Error: User not found')
            raise Exception("User not found")
        
        if user.oauth_token is None or user.oauth_token_secret is None:
            logger.error('Invalid oauth_token or oauth_token_secret')
            raise Exception("Invalid oauth_token or oauth_token_secret")
        
        if user.friends_count == 0:
            self.sent_to_user('Error: You follow 0 users')
            raise Exception("You follow 0 users")
        
        # set the oauth tokens and create the API object
        self.twitter_collector = TwitterCollector(config.CONSUMER_KEY, config.CONSUMER_SECRET, user.oauth_token, user.oauth_token_secret)
        
        # check the remaining hits
        remaining_hits = self.twitter_collector.remaining_hits()
        logger.info('Remaining hits: %s', remaining_hits)
        
        # show a message to user
        self.sent_to_user('Collecting information to build a personalized list of topics...')
        
        # collect the network
        self.get_network(user, max_hits=remaining_hits-80)
        
        # apply ranking and get the top n
        followcounts = Followers.select_top_n(user.id, 2000)
        follow = [d[0] for d in followcounts]
        screen_names = self.get_screen_names(follow[:200])
        
        logger.debug(zip(screen_names[:20], followcounts[:20]))
        
        # show a message to user
        self.sent_to_user("What's Hot on Twitter")
        
        # search for recent statuses (historical data)
        
        try:
            for status in self.twitter_collector.process_search(screen_names):
                self.process_status(status)
        except Exception, e:
            # let's continue, the search part is not essential
            logger.error(str(e), exc_info=True)
        
        # connect and process the streaming api (real-time data)
        
        def status_handler(status):
            self.process_status(status)
        self.twitter_collector.process_streaming(follow, status_handler)
        
        # check the remaining hits
        logger.info('Remaining hits: %s', self.twitter_collector.remaining_hits())
            
    def process_status(self, status):
        if status.status_id in self.status_count:
            count = self.status_count[status.status_id] + status.count
        else:
            count = status.count
        self.status_count[status.status_id] = count
                
        if status.status_id not in self.sent_tweets:
            o = {'type': 'tweet',
                 'text': tweet_parser.parse(status.text).html,
                 'from_user': status.from_user,
                 'name': status.name,
                 'id': status.status_id,
                 'profile_image_url': status.profile_image_url
                 }
            self.send_message(simplejson.dumps(o))
            self.sent_tweets.add(status.status_id)
                
        htlist = TAG_REGEX.findall(status.text)
        for sp, hs, hashtag in htlist:
            
            # increment hashtag counter
            if hashtag in self.hashtags:
                count = self.hashtags[hashtag]
            else:
                count = 0
            self.hashtags[hashtag] = count + 1
            
            # update terms
            terms = set()
            for t in str(status.text).replace(hashtag, '').split(" "):
                term = str(t).translate(None, string.punctuation).lower()
                if len(term)>1 and term not in stop_words:
                    terms.add(lmtzr.lemmatize(term))
            
            if hashtag in self.htref:
                self.htref[hashtag].update(terms)
            else:
                self.htref[hashtag] = set(terms)
                
            # add status to the hashtag
            if hashtag not in self.hashtag_tweets:
                self.hashtag_tweets[hashtag] = set()
            self.hashtag_tweets[hashtag].add(status.status_id)
            
            # send hashtag to the client
            refs = self.htref[hashtag]
            o = {'type':'hashtag',
                 'count':self.hashtags[hashtag],
                 'hashtag':hashtag,
                 'refs':list(refs),
                 'tweets':list(self.hashtag_tweets[hashtag])
                 }
            self.send_message(simplejson.dumps(o))
            
            # send relationship to the client
            o = {'type':'hastag_status',
                 'hashtag': hashtag,
                 'status': status.status_id
                 }
            self.send_message(simplejson.dumps(o))
            
            # find edges for this hashtag
            for hashtag2 in self.hashtags:
                if hashtag2 <> hashtag:
                    refs2 = self.htref[hashtag2]
                    if len(refs.intersection(refs2)) >= 3:
                        edge = {'type':'edge', 'source':hashtag, 'target':hashtag2}
                        self.send_message(simplejson.dumps(edge))
            
        # send status counter to the client
        o = {'type': 'tweet_count',
             'id': status.status_id,
             'count': count
             }
        self.send_message(simplejson.dumps(o))
        
        # TODO: find a better way to limit node size. For now, decreases all topic counters
        htsorted = sorted(self.hashtags.items(), key=operator.itemgetter(1), reverse=True)
        if len(htsorted) > 15 and htsorted[15][1] >= 3:
            o = {'type': 'count_decrease'}
            self.send_message(simplejson.dumps(o))
            for h in self.hashtags:
                self.hashtags[h] -= 1
        
    def get_network(self, user, max_hits=100):
        
        following = Followers.select_by_id(user.id)
        if following is None or len(following) == 0:
            try:
                following = self.twitter_collector.friends_ids(user_id=user.id)
                max_hits -= 1
                Followers.insert_many(user.id, following)
            except UnauthorizedException:
                print 'failed for user ', user.id
                raise Exception('Unable to collect user network: Not authorized to access user %s.'%user.id)
            
        if max_hits <= 0:
            raise Exception('Unable to collect user network: Rate limit reached.')
        
        friends_following = []
        nfriends = len(following)
        for i, friend_id in enumerate(following):
            
            self.sent_to_user('Collecting information to build a personalized list of topics (%s/%s)'%(i,nfriends))
            
            friend = User.select_by_id(friend_id)
            if friend and (friend.blocked == 'Y' or friend.friends_count == 0):
                logger.debug('Not searching for user: %s', friend_id)
                continue
            following = Followers.select_by_id(friend_id)
            if following is None or len(following) == 0:
                try:
                    print 'Getting followers of', friend_id
                    following = self.twitter_collector.friends_ids(user_id=friend_id)
                    if len(following) == 0:
                        if not friend:
                            friend = User()
                        friend.id = friend_id
                        friend.friends_count = len(following)
                        friend.blocked = 'N'
                        User.add(friend)
                    
                    print 'Got %s followers of %s'%(len(following), friend_id)
                    max_hits -= 1
                    Followers.insert_many(friend_id, following)
                except UnauthorizedException:
                    print 'failed for user ', friend_id
                    User.set_blocked(friend_id, 'Y')
                    following = []
            friends_following.append(following)
            if max_hits <= 0: break
            
        commit()
            
    def get_screen_names(self, user_id_list):
        follow_screen_names = []
        to_search = []
        
        # first, get the screen names of users already on the database
        for f_id in user_id_list:
            u = User.select_by_id(f_id)
            if u:
                follow_screen_names.append(u.screen_name)
            else:
                to_search.append(f_id)
                
        # get the remaining screen_names from Twitter
        for twitter_user in self.twitter_collector.get_screen_names(to_search):
            user = User()
            user.id = twitter_user.id
            user.screen_name = twitter_user.screen_name
            user.blocked = 'N'
            user.name = twitter_user.name
            user.description = twitter_user.description
            user.created_at = twitter_user.created_at
            user.friends_count = twitter_user.friends_count
            user.followers_count = twitter_user.followers_count
            user.statuses_count = twitter_user.statuses_count
            user.profile_image_url = twitter_user.profile_image_url
            user.lang = twitter_user.lang
            user.location = twitter_user.location
            User.add(user)
            follow_screen_names.append(user.screen_name)
            print 'inserted %s' % user.screen_name
        
        commit()
        
        return follow_screen_names

    def sent_to_user(self, msg):
        o = {'type': 'title_message', 'value': msg}
        self.send_message(simplejson.dumps(o))