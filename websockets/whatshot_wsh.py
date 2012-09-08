# coding: utf-8
#
#  Copyright (C) 2012 André Panisson
#  You can contact me by email (panisson@gmail.com) or write to:
#  Via Alassio 11/c - 10126 Torino - Italy
#

import simplejson
from mod_pywebsocket._stream_base import ConnectionTerminatedException
import logging
from websockets import core
import threading

logger = logging.getLogger('websocket')
logger.setLevel(logging.DEBUG)

logger.info("Starting websocket")

_GOODBYE_MESSAGE = u'Goodbye from Insight!'

def web_socket_transfer_data(request):
    
    logger.info('#### New connection')
    
    while True:
        try:
            line = request.ws_stream.receive_message()
            if line is None:
                break
            if isinstance(line, unicode):
                if line == _GOODBYE_MESSAGE:
                    return
                else:
                    process_message(request, line)
        except ConnectionTerminatedException:
            break
        except Exception, e:
            logger.error(str(e), exc_info=True)
            #break
        
    logger.info('#### Disconnected')
    
def web_socket_do_extra_handshake(request):
    # This example handler accepts any request. See origin_check_wsh.py for how
    # to reject access from untrusted scripts based on origin value.

    pass  # Always accept.
    
def process_message(request, message):
    logger.debug(message)
    message = simplejson.loads(message)
    
    if 'action' in message and message['action'] == 'connect':
        user = message['screen_name']
        logger.info('Processing request for user ' + user)
        processor = core.Processor(request)
        t = threading.Thread(target=processor.process_user, args=(user,))
        t.start()
        #processor.process_user(user)
