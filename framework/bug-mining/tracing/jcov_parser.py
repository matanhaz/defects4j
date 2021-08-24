import functools
import os
import gc
import shutil
import xml.etree.cElementTree as et
from functools import reduce
from trace_information import Signature, TraceElement, Trace


class JcovParser(object):
    CLOSER = "/>"
    METH = "<meth"
    METHENTER = "<meth"

    def __init__(self, xml_folder_dir=None, files=None, instrument_only_methods=True, short_type=True):
        self.target_dir = None
        if xml_folder_dir:
            self.target_dir = xml_folder_dir
            self.jcov_files = list(filter(os.path.exists, map(lambda name: os.path.join(self.target_dir, name),
                                  filter(lambda name: name.endswith('.xml'), os.listdir(self.target_dir)))))
        else:
            self.jcov_files = files
        self.instrument_only_methods = instrument_only_methods
        self.prefixes = set()
        if self.instrument_only_methods:
            self.prefixes.add(JcovParser.METH)
        self.method_name_by_id, self.method_name_by_extra_slot = self._get_method_ids(short_type)
        self.lines_to_read = self._get_methods_lines()

    def parse(self, delete_dir_when_finished=False):
        for jcov_file in self.jcov_files:
            test_name = os.path.splitext(os.path.basename(jcov_file))[0].lower()
            try:
                yield self._parse_jcov_file(jcov_file, test_name)
            except Exception as e:
                print(e)
        if delete_dir_when_finished:
            shutil.rmtree(self.target_dir)

    def _parse_jcov_file(self, jcov_file, test_name):
        gc.collect()
        trace = self._get_trace_for_file(jcov_file)
        list(map(lambda element: element.set_previous_method(self.method_name_by_extra_slot, self.method_name_by_id), trace.values()))
        return Trace(test_name, trace)

    def _get_trace_for_file(self, jcov_file):
        trace = {}
        for method in self._get_lines_by_inds(jcov_file):
            prefix = list(filter(lambda prefix: method.startswith(prefix), self.prefixes))[0]
            data = dict(list(map(lambda val: val.split('='),
                            method[len(prefix) + 1:-len(JcovParser.CLOSER)].replace('"', "").split())))
            trace_element = TraceElement(data, self.method_name_by_id)
            if trace_element.have_count():
                assert trace_element.id not in trace
                trace[trace_element.id] = trace_element
        return trace

    def _get_lines_by_inds(self, file_path):
        with open(file_path) as f:
            enumerator_next_ind = 0
            for ind in self.lines_to_read:
                list(map(functools.partial(next, f), range(enumerator_next_ind, ind)))
                enumerator_next_ind = ind + 1
                yield next(f).strip()

    def _get_methods_lines(self):
        with open(list(filter(lambda x: 'result' in os.path.basename(x).lower(), self.jcov_files))[0]) as f:
            return list(map(lambda line: line[0], filter(lambda line: any(list(map(lambda prefix: prefix in line[1], self.prefixes))), filter(lambda line: JcovParser.CLOSER in line[1], enumerate(f.readlines())))))

    @staticmethod
    def get_children_by_name(element, name):
        return list(filter(lambda e: e.tag.endswith(name), element.getchildren()))

    @staticmethod
    def get_elements_by_path(root, path):
        elements = [([], root)]
        for name in path:
            elements = reduce(list.__add__,
                              list(map(lambda elem: list(map(lambda child: (elem[0] + [child], child),
                                                   JcovParser.get_children_by_name(elem[1], name))), elements)), [])
        return elements

    def _get_method_ids(self, short_type):
        root = et.parse(list(filter(lambda x: 'result' in os.path.basename(x).lower(), self.jcov_files))[0]).getroot()
        method_ids = {}
        method_slots = {}
        for method_path, method in JcovParser.get_elements_by_path(root, ['package', 'class', 'meth']):
            package_name, class_name, method_name = list(map(lambda elem: elem.attrib['name'], method_path))
            if method_name == '<init>':
                method_name = class_name
            elif method_name == '<clinit>':
                method_name = class_name + "_" + "init"
            method_name = ".".join([package_name, class_name, method_name]) + "({0})".format(
                Signature(method.attrib['vmsig'], short_type).args)
            if self.instrument_only_methods:
                method_ids[int(method.attrib['id'])] = method_name
                method_slots[int(method.attrib['extra_slots'])] = method_name
            else:
                # id = JcovParser.get_elements_by_path(method, ['bl', 'methenter'])[0][1].attrib['id']
                # extra_slot = JcovParser.get_elements_by_path(method, ['bl', 'methenter'])[0][1].attrib['extra_slots']
                method_ids.update(self._get_method_blocks_ids(method, method_name))
        return method_ids, method_slots

    def _get_method_blocks_ids(self, method_et, method_name):
        ids = {}
        for et in method_et.getchildren():
            id = et.attrib.get("id")
            if id:
                prefix = et.tag.split("}")[1]
                self.prefixes.add("<" + prefix)
                ids[int(id)] = method_name + "." + prefix
            else:
                ids.update(self._get_method_blocks_ids(et, method_name))
        return ids


def block_to_comps(block):
    splitted = block.split(".")
    package_name = ".".join(splitted[:-3])
    class_name = ".".join(splitted[:-2])
    function_name = ".".join(splitted[:-1])
    block_name = ".".join(splitted)
    return [package_name, class_name, function_name, block_name]


def findPathsNoLC(G,u,n):
    if n==0:
        return [[u]]
    paths = []
    for neighbor in G.neighbors(u):
        for path in findPathsNoLC(G,neighbor,n-1):
            if u not in path:
                paths.append([u]+path)
    return paths


if __name__ == '__main__':
    t = list(JcovParser(None, [r"C:\Users\amirelm\Downloads\bug-mining (20)\bug-mining_19\framework\projects\Lang\result.xml"], True, True).parse(False))[
        0]
    traces = t.split_to_subtraces()
    from collections import Counter
    from networkx import DiGraph, single_source_shortest_path_length
    import networkx as nx
    import json
    e = t.get_call_graph_edges()
    c = Counter(e)
    g = DiGraph()
    g.add_edges_from(e, count=dict(c))
    possible_pairs = []
    paths = {}
    # allpaths = []
    # for node in g:
    #     allpaths.extend(findPathsNoLC(g, node, 3))
    for n in g.node:
        if not n.split('.')[-1].startswith('test'):
            continue
        for k, v in single_source_shortest_path_length(g, n).items():
            if k == n:
                continue
            possible_pairs.append((n, k, v))
            paths[(n, k, v)] = list(nx.all_simple_paths(g, source=n, target=k))
    with open(r'z:\temp\paths.json', 'w') as f:
        f.write(json.dumps(list(paths.items())))
    pass
