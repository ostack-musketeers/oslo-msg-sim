import eventlet
eventlet.monkey_patch()

import logging
import os
import sys
import uuid

from eventlet.green import zmq
from eventlet.event import Event

log = logging.getLogger("sim.stem")


class StemCell(object):

    def __init__(self, zmq_ctx, ctrl_endpoint):
        self.zmq_ctx = zmq_ctx
        # Request / Reply for stem cell querying against ctrl api.
        self.ctrl_endpoint = ctrl_endpoint
        self.ctrl_server = None

        # Pub / Sub for mass communication from controller (ie. shutdown).
        self.ctrl_bus_endpoint = None
        self.ctrl_bus = None

        # Directed / msg by role (load balanced)
        self.ctrl_msg_endpoint = None
        self.ctrl_role_msg = None

        # Role this stem cell will take within the simulation
        self.role = None

        # Unique identity for cell
        self.id = uuid.uuid4().hex

        # Registration data from control server
        self.registration = None

        self.threads = []
        self.stop_evt = Event()

    def connect(self):
        self.ctrl_server = self.zmq_ctx.socket(zmq.REQ)
        self.ctrl_server.connect(self.ctrl_endpoint)

    def register(self):
        assert self.role is None
        self.ctrl_server.send_json({'op': 'register', 'id': self.id})

        self.registration = self.ctrl_server.recv_json()

        self.role = self.registration.get('role')

        self.ctrl_bus = self.zmq_ctx.socket(zmq.SUB)
        self.ctrl_bus.connect(self.registration['pub_endpoint'])
        for s in self.registration.get('subscriptions', ("",)):
            self.ctrl_bus.setsockopt(zmq.SUBSCRIBE, s)

        self.threads.append(eventlet.spawn(self.handle_sub_msg))

        self.ctrl_role_msg = self.zmq_ctx.socket(zmq.PULL)
        self.ctrl_role_msg.connect(self.registration['msg_endpoint'])

        self.threads.append(eventlet.spawn(self.handle_role_msg))

        log.info("Stem registered %s", self.registration)

    def handle_sub_msg(self):
        while True:
            msg = self.ctrl_bus.recv_json()
            log.debug("bus msg received %s", msg)
            if msg.get('op', '') == 'shutdown':
                self.stop_evt.send(True)

    def handle_role_msg(self):
        while True:
            msg = self.ctrl_role_msg.recv_json()
            log.debug("role msg received %s", msg)

    def run(self):
        log.info("Connecting to server")
        self.connect()
        self.register()
        log.info("Stem cell running")
        self.stop_evt.wait()
        log.info("Stopping cell")
        self.stop()

    def stop(self):
        self.ctrl_server.close()
        for s in self.registration.get('subscriptions', ()):
            self.ctrl_bus.setsockopt(zmq.UNSUBSCRIBE, s)

        for t in self.threads:
            t.kill()

        self.ctrl_bus.close()
        self.ctrl_role_msg.close()
        self.threads = []
        self.zmq_ctx.term()
        sys.exit()


def main():
    logging.basicConfig(level=logging.DEBUG)
    endpoint = os.environ.get('STEM_CONTROL_ENDPOINT', 'tcp://127.0.0.1:3900')
    ctx = zmq.Context(1)
    cell = StemCell(ctx, endpoint)
    cell.run()


if __name__ == '__main__':
    main()
