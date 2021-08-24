import re
from functools import reduce


class PrimitiveTypes(object):
    PRIMITIVES = {'Z': "boolean", 'V': "void", 'I': "int", 'J': "long", 'C': "char", 'B': "byte", 'D': "double",
                  'S': "short", 'F': "float"}

    @staticmethod
    def get_primitive_type(primitive):
        return PrimitiveTypes.PRIMITIVES[primitive]


class Signature(object):
    MATCHER = re.compile("\\(([^\\)]*)\\)(.*)")

    def __init__(self, vmsig, short_type=False):
        self.vmsig = vmsig
        m = Signature.MATCHER.match(self.vmsig)
        self.return_value = Signature.convert_vm_type(m.group(2))
        self.args = Signature.get_args(m.group(1), short_type)

    @staticmethod
    def convert_vm_type(vm_type):
        return Signature.get_type_name(vm_type.replace('/', '.').replace('$', '.'))

    @staticmethod
    def get_type_name(vm_type):
        dims = 0
        while vm_type[dims] == '[':
            dims += 1
        type = ''
        if vm_type[dims] == 'L':
            type = vm_type[dims + 1: len(vm_type) - 1]
        else:
            type = PrimitiveTypes.get_primitive_type(vm_type[dims])
        return type + "[]" * dims

    @staticmethod
    def get_args(descr, short_type=False):
        if descr == "":
            return descr
        pos = 0
        last_pos = len(descr)
        args = ''
        dims = 0
        while pos < last_pos:
            ch = descr[pos]
            if ch == 'L':
                delimPos = descr.find(';', pos)
                if delimPos == -1:
                    delimPos = last_pos
                type = Signature.convert_vm_type(descr[pos: delimPos + 1])
                pos = delimPos + 1
            elif ch == '[':
                dims += 1
                pos += 1
                continue
            else:
                type = PrimitiveTypes.get_primitive_type(ch)
                pos += 1
            if short_type:
                type = type.split('.')[-1]
            args += type + "[]" * dims
            dims = 0
            if pos < last_pos:
                args += ';'
        return args


class HitInformation(object):
    def __init__(self, method_name, lst):
        assert len(lst) == 6
        self.method_name = method_name
        self.count, self.previous_slot, self.parent, self.test_slot, self.test_parent, self.test_previous = lst

    def set_previous_method(self, method_name_by_slot, method_name_by_id):
        self.previous_method = method_name_by_slot.get(self.previous_slot, method_name_by_id.get(self.previous_slot, 'None'))
        self.parent_method = method_name_by_slot.get(self.parent, method_name_by_id.get(self.parent, 'None'))
        self.execution_edge = (self.previous_method, self.method_name)
        self.call_graph_edge = (self.parent_method, self.method_name)

    @staticmethod
    def read_hit_information_string(str, method_name):
        return list(map(lambda lst: HitInformation(method_name, lst), eval(str)))


class TraceElement(object):
    def __init__(self, jcov_data, method_name_by_id):
        self.jcov_data = jcov_data
        self.id = int(self.jcov_data['id'])
        extra_slot = int(self.jcov_data['extra_slots'])
        if extra_slot != -1:
            self.extra_slot = extra_slot
        self.count = int(self.jcov_data['count'])
        self.method_name = method_name_by_id[self.id]
        self.hits_information = []
        if self.count:
            self.hits_information = HitInformation.read_hit_information_string(self.jcov_data['HitInformation'], self.method_name)
            # assert sum(map(lambda x: x.count, self.hits_information)) == self.count, "{0}-{1}, {2}".format(self.id, self.method_name, self.count)

    def set_previous_method(self, method_name_by_slot, method_name_by_id):
        list(map(lambda hit: hit.set_previous_method(method_name_by_slot, method_name_by_id), self.hits_information))

    def have_count(self):
        return self.count != 0

    def get_trace(self, trace_granularity='methods'):
        if trace_granularity == 'methods':
            return self.method_name
        elif trace_granularity == 'files':
            return ".".join((self.method_name.split("(")[0].split(".")[:-1]))
        assert False

    def get_execution_edges(self):
        return list(map(lambda hit: hit.execution_edge, self.hits_information))

    def get_call_graph_edges(self):
        return list(map(lambda hit: hit.call_graph_edge, self.hits_information))

    def get_execution_edges_num(self):
        return list(map(lambda hit: (hit.previous_slot, self.extra_slot), self.hits_information))

    def get_call_graph_edges_num(self):
        return list(map(lambda hit: (hit.parent, self.extra_slot), self.hits_information))

    def split_by_tests_slots(self):
        traces = {}
        tests = {}
        for h in self.hits_information:
            if h.test_slot != -1:
                tests.setdefault((h.test_slot, h.test_parent, h.test_previous), []).append(h)
        for t in tests:
            trace = TraceElement(self.jcov_data, {self.id: self.method_name})
            trace.hits_information = tests[t]
            trace.count = sum(list(map(lambda h: h.count, tests[t])))
            traces[t] = (trace.id, trace)
        return traces


class Trace(object):
    def __init__(self, test_name, trace):
        self.test_name = test_name
        self.trace = trace

    def get_trace(self, trace_granularity='methods'):
        return list(set(map(lambda t: self.trace[t].get_trace(trace_granularity).lower().replace("java.lang.", "").replace("java.io.", "").replace("java.util.", ""), self.trace)))

    def get_execution_edges(self):
        return set(reduce(list.__add__, list(map(lambda element: element.get_execution_edges(), self.trace.values())), []))

    def get_call_graph_edges(self):
        return set(reduce(list.__add__, list(map(lambda element: element.get_call_graph_edges(), self.trace.values())), []))

    def get_execution_edges_num(self):
        return set(reduce(list.__add__, list(map(lambda element: element.get_execution_edges_num(), self.trace.values())), []))

    def get_call_graph_edges_num(self):
        return set(reduce(list.__add__, list(map(lambda element: element.get_call_graph_edges_num(), self.trace.values())), []))

    def split_to_subtraces(self):
        tests = list(filter(lambda x: x.method_name.split('.')[-2].endswith('Test') and x.method_name.split('.')[-1].startswith('test'), list(self.trace.values())))
        tests_slots = {}
        renames = {}
        for t in tests:
            if len(t.hits_information) == 0:
                continue
            key = (t.id, t.hits_information[0].parent, t.hits_information[0].previous_slot)
            tests_slots[key] = t
            for h in t.hits_information:
                renames[(t.id, h.parent, h.previous_slot)] = key
                renames[(t.extra_slot, h.parent, h.previous_slot)] = key
        # tests_slots = dict(list(map(lambda x: ((x.id, x.hits_information[0].parent, x.hits_information[0].previous_slot), x), tests)) + list(map(lambda x: ((x.extra_slot, x.hits_information[0].parent, x.hits_information[0].previous_slot), x), tests)))
        test_traces = {}
        traces = {}
        for t in tests:
            test_traces[t.method_name] = []
        for trace in self.trace:
            sub_traces = self.trace[trace].split_by_tests_slots()
            for st in sub_traces:
                if tests_slots.get(renames.get(st)):
                    test_traces[tests_slots[renames[st]].method_name].append(sub_traces[st])
        for t in test_traces:
            if test_traces[t]:
                traces[t] = Trace(t, dict(test_traces[t]))
        # fix prev method
        for t in traces:
            trace = traces[t]
            ids = {}
            slots = {}
            for e in trace.trace.values():
                ids[e.id] = e.method_name
                slots[e.extra_slot] = e.method_name
            for e in trace.trace.values():
                e.set_previous_method(slots, ids)
        return traces
