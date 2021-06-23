import logging
import json
from enum import Enum
from logging.handlers import TimedRotatingFileHandler
from threading import Thread

from jsonrpc import JSONRPCResponseManager, dispatcher
from werkzeug.serving import run_simple
from werkzeug.wrappers import Request, Response

from .utils import CustomFormatter, log, playing, rpc

_logger = logging.getLogger('werkzeug')

if log.to_file and log.path != 'none':
    if log.path.is_dir():
        _logger = log.path.joinpath('jsonrpc.log')

    _format = logging.Formatter('[%(asctime)s] [%(levelname)s]  %(message)s')
    file_handler = TimedRotatingFileHandler(_logger, when='midnight',
                                            backupCount=log.backup_count)

    file_handler.setFormatter(_format)
    _logger.addHandler(file_handler)
else:
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(CustomFormatter())
    _logger.addHandler(console_handler)


@dispatcher.add_method
def now_broadcasting(**kwargs):
    playing.now['probe'] = playing.now['probe'].to_json()

    if playing.previous.get('probe'):
        playing.previous['probe'] = playing.previous['probe'].to_json()

    if playing.next.get('probe'):
        playing.next['probe'] = playing.next['probe'].to_json()

    return {
        'now': playing.now,
        'previous': playing.previous,
        'next': playing.next
        }


@Request.application
def application(request):
    # Dispatcher is dictionary {<method_name>: callable}
    response = JSONRPCResponseManager.handle(
        request.get_data(cache=False, as_text=True), dispatcher)
    return Response(response.json, mimetype='application/json')


def run_rpc_server():
    rpc_thread = Thread(target=run_simple,
                        args=(rpc.addr, rpc.port, application))
    rpc_thread.daemon = True
    rpc_thread.start()


if __name__ == '__main__':
    run_rpc_server()
