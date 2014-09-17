import eventlet

eventlet.monkey_patch()

from eventlet.green import zmq
from eventlet.event import Event

import logging
import os
import socket
import signal
import yaml

from app import Simulation
import workflows

log = logging.getLogger('msg.ctrl')


class SimController(object):

    def __init__(self, zmq_ctx, ctrl_endpoint):
        self.zmq_ctx = zmq_ctx

        # Request / Reply for stem cell querying against ctrl api.
        self.ctrl_endpoint = ctrl_endpoint
        self.ctrl_server = None

        # Pub / Sub for mass communication from controller (ie. shutdown).
        self.ctrl_bus_endpoint = None
        self.ctrl_bus = None

        # Directed / msg by role (load balanced)
        self.role_endpoints = {}
        self.ctrl_role_msg = None

        self.threads = []
        self.stop_evt = Event()

        self.sim = Simulation()
        with open(
            os.path.join(
                os.path.dirname(
                    os.path.abspath(workflows.__file__)),
                'role-map.yml')) as fh:
            self.role_data = yaml.safe_load(fh.read())

        self.sim.load_roles(self.role_data['roles'])

    def start(self):
        log.info("Starting server")

        self.ctrl_server = self.zmq_ctx.socket(zmq.REP)
        self.ctrl_server.bind(self.ctrl_endpoint)

        port = get_unused_port()
        self.ctrl_bus_endpoint = "tcp://127.0.0.1:%s" % port
        self.ctrl_bus = self.zmq_ctx.socket(zmq.PUB)
        self.ctrl_bus.bind(self.ctrl_bus_endpoint)

        port = get_unused_port()
        self.role_endpoint = "tcp://127.0.0.1:%s" % port
        self.ctrl_role_msg = self.zmq_ctx.socket(zmq.PUSH)
        self.ctrl_role_msg.bind(self.role_endpoint)

        self.threads.append(eventlet.spawn(self.handle_request))
        self.threads.append(eventlet.spawn(self.handle_heartbeat))
        # Start our green threads
        eventlet.sleep(0)

    def stop(self):
        self.running = False
        self.stop_evt.send(True)
        log.info("Sending shutdown msg to stems")
        self.ctrl_bus.send_json({'op': 'shutdown'})
        self.ctrl_bus.send_json({'op': 'shutdown'})
        self.ctrl_server.close()
        self.ctrl_role_msg.close()
        self.ctrl_bus.close()

        for t in self.threads:
            t.kill()

        self.threads = []
        self.zmq_ctx.term()

    def run(self):
        self.running = True
        log.info("Running server")
        self.start()

        log.info("Waiting")
        self.stop_evt.wait()
        log.info("Stopping server")

    def handle_heartbeat(self):
        while True:
            log.info("Sending heartbeat")
            self.ctrl_bus.send_json({'op': 'heartbeat'})
            log.info("Sent heartbeat")
            eventlet.sleep(2)
            log.info("Post sleep heartbeat")

    def handle_request(self):
        while self.running:
            log.info("Waiting for request")
            req = self.ctrl_server.recv_json()
            log.info("Handling request %s", req)
            if req.get('op', '') == 'register':
                self.handle_registration(req)

    def handle_registration(self, req):
        response = {}
        response['role'] = self.sim.register_stem(req)
        response['pub_endpoint'] = self.ctrl_bus_endpoint
        response['msg_endpoint'] = self.role_endpoint
        self.ctrl_server.send_json(response)


def get_unused_port():
    """Returns an unused port on localhost."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('localhost', 0))
    port = s.getsockname()[1]
    s.close()
    return port


def main():
    logging.basicConfig(
        format="%(asctime)s:%(levelname)s:%(name)s:%(threadName)s:%(message)s",
        level=logging.DEBUG)
    endpoint = os.environ.get(
        'STEM_CONTROL_ENDPOINT', 'tcp://127.0.0.1:3900')
    ctx = zmq.Context()

    controller = SimController(ctx, endpoint)

    def signal_handler(s, f):
        log.info("Signal received stopping")
        controller.stop()
    signal.signal(signal.SIGINT, signal_handler)

    controller.run()


if __name__ == '__main__':
    main()
