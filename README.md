Description
-----------

Twitter produces daily an incredible amount of real-time information, but lacks of an effective tool 
to explore which topics are being discussed by users with similar interests. 
This tool uses an augmented network of Twitter's following users to build a personalized, 
dynamic and interactive list of hot topics.

Dependencies
------------

Core dependencies:
- sqlalchemy

Websockets server:
- mod_pywebsocket
- tweepy
- simplejson
- nltk WordNet Lemmatizer
- twitter-text-python

Web server:
- Flask
- OAuth

Installation
-------
First, clone this repository:

```
$ git clone git://github.com/panisson/whatshot.git
```

You must have a valid Twitter consumer key and consumer secret to run this application.
If you don't have one, go to dev.twitter.com and register a new application.

The data tables for the MySQL database can be created using the SQL in the file 'db.sql'.

After setting the database, change the file 'config.py' with your Twitter consumer key and consumer secret
and with the credentials for the MySQL database.

Make sure all dependencies are installed. 
For mod_pywebsocket, go to the repository directory and get the mod_pywebsocket package by running:

```
$ svn checkout http://pywebsocket.googlecode.com/svn/trunk/src/mod_pywebsocket mod_pywebsocket
```

To start the websockets server, run the pywebsocket standalone server with the command:

```
$ export PYTHONPATH=. && python mod_pywebsocket/standalone.py -m handler_map.txt -p 8880 -d websockets --log-level=info
```

To start the Web server, run:
```
$ export PYTHONPATH=. && python whatshot/app.py
```

Contributing
------------
If you have a Github account please fork the repository,
create a topic branch, and commit your changes.
Then submit a pull request from that branch.

License
-------
Written by André Panisson <panisson@gmail.com>  
Copyright (C) 2012 André Panisson  
You can contact me by email (panisson@gmail.com) or write to:  
André Panisson, ISI Foundation, Via Alassio 11/c, 10126 Torino, Italy.
