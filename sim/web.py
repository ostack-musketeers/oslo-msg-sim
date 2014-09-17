import eventlet
from eventlet import wsgi

eventlet.monkey_patch()

from flask import (
    Flask, render_template)

app = Flask('msgsim')


@app.route("/")
def index():
    return render_template('index.j2')


def start_server(controller):
    listener = eventlet.listen(('0.0.0.0', 8080))
    app.controller = controller
    wsgi.server(listener, app)
