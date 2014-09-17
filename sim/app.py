import itertools
import random


class Simulation(object):

    def __init__(self):
        self.stems = {}  # map stem id -> stem info
        self.roles = {}  # map of roles -> list of stem ids
        self.instances = {}
        self.role_populations = []

    def load_roles(self, role_map):
        for k, v in role_map.items():
            if k in self.roles:
                continue
            self.roles.setdefault(k, [])
            self.role_populations.extend([k] * v['ratio'])

    def register_stem(self, stem_info):
        self.stems[stem_info['id']] = stem_info
        return self.assign_stem_role(stem_info['id'])

    def assign_stem_role(self, stem_id):
        distrib = self._get_role_distribution()
        for k, v in distrib.items():
            if v == 0:
                self.roles[k].append(stem_id)
                return k
        k = random.choice(self.role_populations)
        self.roles[k].append(stem_id)
        return k

    def _get_role_distribution(self):
        distrib = dict(zip(self.roles, itertools.repeat(0)))
        for k in self.roles:
            distrib[k] = len(self.roles[k])
        return distrib

    def start_msg_flow(self, name):
        pass

    def end_msg_flow(self, workflow_id):
        pass

    def active_msg_flow(self):
        pass
