# coding: utf-8
#
#  Copyright (C) 2012 André Panisson
#  You can contact me by email (panisson@gmail.com) or write to:
#  Via Alassio 11/c - 10126 Torino - Italy
#
from flask import request, redirect, url_for, session
from flaskext.oauth import OAuth
import flask, tweepy
from whatshot import config
from model import User, commit
import logging

# setup flask
app = flask.Flask(__name__)
app.debug = config.DEBUG
app.secret_key = config.SECRET_KEY
oauth = OAuth()

# add the flask log handlers to sqlalchemy
loggers = [logging.getLogger('sqlalchemy.engine'),
           logging.getLogger('sqlalchemy.orm.unitofwork')]
for logger in loggers:
    for handler in app.logger.handlers:
        logger.addHandler(handler)

# uncomment this to enable sqlalchemy logging
#logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
#logging.getLogger('sqlalchemy.orm.unitofwork').setLevel(logging.DEBUG)

twitter = oauth.remote_app('twitter',
    # unless absolute urls are used to make requests, this will be added
    # before all URLs.  This is also true for request_token_url and others.
    base_url='http://api.twitter.com/1/',
    # where flask should look for new request tokens
    request_token_url='https://api.twitter.com/oauth/request_token',
    # where flask should exchange the token with the remote application
    access_token_url='https://api.twitter.com/oauth/access_token',
    # twitter knows two authorizatiom URLs.  /authorize and /authenticate.
    # they mostly work the same, but for sign on /authenticate is
    # expected because this will give the user a slightly different
    # user interface on the twitter side.
    authorize_url='https://api.twitter.com/oauth/authenticate',
    # the consumer keys from the twitter application registry.
    consumer_key=config.CONSUMER_KEY,
    consumer_secret=config.CONSUMER_SECRET,
#    consumer_key='foa0YuAxJTiHHmaUlN5Q',
#    consumer_secret='dzQjFTp3X69JXHoGthg2XfjCrdQ8waOlvXq6igbXmQ'
)

@twitter.tokengetter
def get_twitter_token():
    """This is used by the API to look for the auth token and secret
    it should use for API calls.  During the authorization handshake
    a temporary set of token and secret is used, but afterwards this
    function has to return the token and secret.  If you don't want
    to store this in the database, consider putting it into the
    session instead.
    """
    if 'screen_name' in flask.session:
        return flask.session['oauth_token'], flask.session['oauth_token_secret']

@app.route('/')
def index():
    # app.logger.debug(request.url_rule.endpoint)
    if 'screen_name' in flask.session:
        return flask.render_template('main.html')
    else:
        return flask.render_template('index.html')

@app.route('/login')
def login():
    """Calling into authorize will cause the OpenID auth machinery to kick
    in.  When all worked out as expected, the remote application will
    redirect back to the callback URL provided.
    """
    return twitter.authorize(callback=url_for('oauth_authorized',
        next=request.args.get('next') or request.referrer or None))

@app.route('/logout')
def logout():
    session.pop('screen_name', None)
    return redirect(request.referrer or url_for('index'))

@app.route('/oauth-authorized')
@twitter.authorized_handler
def oauth_authorized(resp):
    """Called after authorization.  After this function finished handling,
    the OAuth information is removed from the session again.  When this
    happened, the tokengetter from above is used to retrieve the oauth
    token and secret.

    Because the remote application could have re-authorized the application
    it is necessary to update the values in the database.

    If the application redirected back after denying, the response passed
    to the function will be `None`.  Otherwise a dictionary with the values
    the application submitted.  Note that Twitter itself does not really
    redirect back unless the user clicks on the application name.
    """
    next_url = request.args.get('next') or url_for('index')
    if resp is None:
        #TODO: show friendly message
        #flash(u'You denied the request to sign in.')
        return redirect(next_url)

    screen_name = resp['screen_name']
    oauth_token = resp['oauth_token']
    oauth_token_secret = resp['oauth_token_secret']
    
    user = User.select_by_screen_name(screen_name)
    if not user:
        app.logger.debug('User not found on database. Using the Twitter API')
        auth = tweepy.OAuthHandler(config.CONSUMER_KEY, config.CONSUMER_SECRET)
        auth.set_access_token(oauth_token, oauth_token_secret)
        api = tweepy.API(auth)
        twitter_user = api.get_user(screen_name=screen_name)
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
        user.oauth_token = oauth_token
        user.oauth_token_secret = oauth_token_secret
        User.add(user)
    else:
        user.oauth_token = oauth_token
        user.oauth_token_secret = oauth_token_secret

    flask.session['screen_name'] = resp['screen_name']
    flask.session['oauth_token'] = resp['oauth_token']
    flask.session['oauth_token_secret'] = resp['oauth_token_secret']
    
    commit()
    
    return flask.redirect(next_url)

@app.route('/about')
def about():
    return flask.render_template('about.html')

if __name__ == "__main__":
    # Starting flask
    app.run(host='0.0.0.0', port=8080)
    