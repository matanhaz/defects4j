import json
import os
import socket
import sys
import xml.etree.cElementTree as et
from subprocess import Popen, PIPE, run

import networkx as nx
from junitparser import JUnitXml

from jcov_parser import JcovParser

et.register_namespace('', "http://maven.apache.org/POM/4.0.0")
et.register_namespace('xsi', "http://www.w3.org/2001/XMLSchema-instance")
try:
    import javadiff.javadiff.diff as diff
except:
    try:
        import javadiff.diff as diff
    except:
        pass
try:
    from sfl.sfl.Diagnoser.diagnoserUtils import write_json_planning_file
except:
    pass
from functools import reduce


class TestResult(object):
    def __init__(self, junit_test, suite_name=None, report_file=None):
        self.junit_test = junit_test
        self.classname = junit_test.classname or suite_name
        self.name = junit_test.name
        self.time = junit_test.time
        self.full_name = "{classname}.{name}".format(classname=self.classname, name=self.name)
        self.report_file = report_file
        self.outcome = 'pass'
        if junit_test.result:
            self.outcome = junit_test.result[0]._tag

    def __repr__(self):
        return "{full_name}: {outcome}".format(full_name=self.full_name, outcome=self.outcome)

    def set_failure(self, fail):
        if fail:
            self.outcome = 'failure'
        else:
            self.outcome = 'pass'

    def is_passed(self):
        return self.outcome == 'pass'

    def get_observation(self):
        return 0 if self.is_passed() else 1

    def as_dict(self):
        return {'_test_name': self.full_name, '_outcome': self.outcome}


class Tracer:
    JCOV_JAR_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "externals", "jcov.jar")
    CALL_GRAPH_JAR_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "externals",
                                       "javacg-0.1-SNAPSHOT-static.jar")

    def __init__(self, repo_path, trace_type, ind=0):
        self.trace_type = trace_type
        self.command_port = 5552
        self.agent_port = 5551
        self.repo_path = repo_path
        self.xml_path = os.path.join(self.repo_path, 'build.xml')
        if os.path.isfile(os.path.join(self.repo_path, 'maven-build.xml')):
            self.xml_path = os.path.join(self.repo_path, 'maven-build.xml')
        self.path_to_result_file = os.path.abspath(f"result_{self.trace_type}.xml")
        self.path_to_out_template = os.path.abspath(f"template_{self.trace_type}.xml")
        self.path_to_classes_file = os.path.abspath(f"classes_{self.trace_type}")
        self.path_to_tests_details = os.path.abspath(f"test_details_{self.trace_type}.json")
        self.path_to_tests_results = os.path.abspath(f"test_results_{self.trace_type}.json")
        self.bugs_file = os.path.abspath('bugs.json')
        self.call_graph_path = os.path.abspath('call_graph.gexf')
        self.call_graph_tests_path = os.path.abspath('call_graph_tests.json')
        self.call_graph_nodes_path = os.path.abspath('call_graph_nodes.json')
        self.tests_to_exclude_path = os.path.abspath('tests_to_exclude.json')
        self.trigger_tests_path = os.path.abspath('trigger_tests.json')
        self.tests_run_log = os.path.abspath('tests_run_log')

        if self.trace_type == 'sanity':
            self.matrix = os.path.abspath(f"matrix_{self.trace_type}.json")
        else:
            self.matrix = os.path.abspath(f"matrix_{ind}_{self.trace_type}.json")
        self.test_results = {}
        self.tests_to_run = None
        self.tests_to_exclude = None
        self.classes_to_trace = None
        self.set_by_trace_type()

    def set_by_trace_type(self):
        if os.path.exists(self.tests_to_exclude_path):
            with open(self.tests_to_exclude_path) as f:
                exclude = json.loads(f.read())
            self.tests_to_exclude = list(set(map(lambda t: f"**/{t.split('.')[-2]}.java", exclude)))
        bugs = []
        if not os.path.exists(self.bugs_file):
            return
        if not os.path.exists(self.call_graph_tests_path):
            return
        with open(self.bugs_file) as f:
            bugs = list(set(map(lambda x: '.'.join(x.split('.')[:-1]), json.loads(f.read()))))
        tests_classes = list(set(map(lambda x: '.'.join(x.split('.')[:-1]), self.get_trigger_tests())))
        with open(self.call_graph_tests_path) as f:
            relevant_tests = json.loads(f.read())
        with open(self.call_graph_nodes_path) as f:
            relevant_nodes = json.loads(f.read())
        if self.trace_type == 'sanity':
            self.classes_to_trace = bugs + tests_classes
            self.tests_to_run = list(set(map(lambda t: f"**/{t.split('.')[-1]}.java", tests_classes)))
        elif self.trace_type == 'full':
            self.classes_to_trace = list(set(relevant_nodes))
            self.tests_to_run = list(set(map(lambda t: f"**/{t.split('.')[-1]}.java", relevant_tests)))

    def set_junit_formatter(self):
        self.set_junit_formatter_file(self.xml_path)

    def set_junit_props(self):
        self.set_junit_properties(self.xml_path)

    # def collect_failed_tests(self, failed_tests_file):
    #     trigger_tests = []
    #     with open(failed_tests_file) as f:
    #         lines = list(f.readlines())
    #         for ind, line in filter(lambda l: l[1].startswith('---'), enumerate(lines)):
    #             trigger = line[4:-1]
    #             if '::' in trigger:
    #                 trigger = trigger.split('[')[0]
    #                 trigger = trigger.replace('::', '.')
    #                 # else:
    #                 #     trigger = trigger + '.NOTEST'
    #                 if 'test' in trigger.lower():
    #                     trigger_tests.append(trigger)
    #     with open(self.tests_to_exclude_path, 'w') as f:
    #         json.dump(list(set(trigger_tests)), f)
    #     with open(self.tests_run_log, 'w') as f:
    #         f.writelines(lines)

    def exclude_tests(self):
        if not self.tests_to_exclude:
            print("not tests to exclude")
            return
        element_tree = et.parse(self.xml_path)
        junit = list(filter(lambda x: x.tag == 'junit', element_tree.iter()))
        if junit:
            for junit_element in junit:
                batchtest = list(filter(lambda x: x.tag == 'batchtest', junit_element.iter()))
                for b in batchtest:
                    fileset = list(filter(lambda x: x.tag == 'fileset', b.iter()))[0]
                    for t in self.tests_to_exclude:
                        exclude = et.SubElement(fileset, 'exclude')
                        exclude.attrib.update({'name': t})
        element_tree.write(self.xml_path, xml_declaration=True)
        tests = list(set(map(lambda x: x.replace('.java', '').replace('**/', '').lower(), self.tests_to_exclude)))
        print(f"tests to remove {tests}")
        for root, _, files in os.walk(os.path.dirname(self.xml_path)):
            for f in filter(lambda x: (x.endswith('.java') or x.endswith('.class')) and 'test' in x.lower(), files):
                for t in tests:
                    if t in f.lower():
                        try:
                            if os.path.exists(os.path.join(root, f)):
                                print("remove test file " + os.path.join(root, f))
                                os.remove(os.path.join(root, f))
                        except Exception as e:
                            print(e)

    def set_junit_formatter_file(self, xml_path):
        element_tree = et.parse(xml_path)
        junit = list(filter(lambda x: x.tag == 'junit', element_tree.iter()))
        if junit:
            for j in junit:
                j.attrib.update({'fork': 'true', 'forkmode': 'once', 'haltonerror': 'false', 'haltonfailure': 'false'})
                formatter = list(filter(lambda x: x.tag == 'formatter', j.iter()))
                if formatter:
                    formatter = formatter[0]
                else:
                    formatter = et.SubElement(j, 'formatter')
                formatter.attrib.update({'type': 'xml', 'usefile': 'true'})

                jvmarg = list(filter(lambda x: x.tag == 'jvmarg', j.iter()))
                if jvmarg:
                    jvmarg = jvmarg[0]
                else:
                    jvmarg = et.SubElement(j, 'jvmarg')
                arg_line = r'-javaagent:{JCOV_JAR_PATH}=grabber,port={PORT},include_list={CLASSES_FILE},template={OUT_TEMPLATE},type=method'.format(
                    JCOV_JAR_PATH=Tracer.JCOV_JAR_PATH, PORT=self.agent_port, CLASSES_FILE=self.path_to_classes_file,
                    OUT_TEMPLATE=self.path_to_out_template)
                jvmarg.attrib.update({'value': arg_line})
                if self.tests_to_run or self.tests_to_exclude:
                    self.set_junit_tests(j)
        element_tree.write(xml_path, xml_declaration=True)

    def set_junit_properties(self, xml_path):
        element_tree = et.parse(xml_path)
        junit = list(filter(lambda x: x.tag == 'junit', element_tree.iter()))
        if junit:
            for j in junit:
                j.attrib.update({'fork': 'true', 'forkmode': 'once', 'haltonerror': 'false', 'haltonfailure': 'false'})
                formatter = list(filter(lambda x: x.tag == 'formatter', j.iter()))
                if formatter:
                    formatter = formatter[0]
                else:
                    formatter = et.SubElement(j, 'formatter')
                formatter.attrib.update({'type': 'xml', 'usefile': 'true'})
        element_tree.write(xml_path, xml_declaration=True)

    def set_junit_tests(self, junit_element):
        batchtest = list(filter(lambda x: x.tag == 'batchtest', junit_element.iter()))
        for b in batchtest:
            fileset = list(filter(lambda x: x.tag == 'fileset', b.iter()))[0]
            includes = list(filter(lambda x: x.tag == 'include', fileset.iter()))
            excludes = list(filter(lambda x: x.tag == 'exclude', fileset.iter()))
            for i in includes:
                fileset.remove(i)
            if self.tests_to_run:
                for t in self.tests_to_run:
                    include = et.SubElement(fileset, 'include')
                    include.attrib.update({'name': t})
            if self.tests_to_exclude:
                for t in self.tests_to_exclude:
                    exclude = et.SubElement(fileset, 'exclude')
                    exclude.attrib.update({'name': t})

    def get_classes_path(self):
        all_classes = {os.path.dirname(self.xml_path)}
        for root, dirs, files in os.walk(os.path.dirname(self.xml_path)):
            for f in files:
                if f.endswith('class'):
                    all_classes.add(root)
                    break
        return all_classes

    def template_creator_cmd_line(self):
        cmd_line = ["java", '-Xms2g', '-jar', Tracer.JCOV_JAR_PATH, 'tmplgen', '-verbose', '-t',
                    self.path_to_out_template, '-c', self.path_to_classes_file, '-type', 'method']
        # if self.classes_to_trace:
        #     for c in self.classes_to_trace:
        #         cmd_line.extend(['-i', c])
        cmd_line.extend(self.get_classes_path())
        return cmd_line

    def grabber_cmd_line(self):
        cmd_line = ["java", '-Xms2g', '-jar', Tracer.JCOV_JAR_PATH, 'grabber', '-vv', '-port', self.agent_port,
                    '-command_port', self.command_port, '-t', self.path_to_out_template, '-o', self.path_to_result_file]
        return list(map(str, cmd_line))

    def check_if_grabber_is_on(self):
        import time
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            time.sleep(5)
            s.connect(('127.0.0.1', int(self.command_port)))
            s.close()
            return True
        except:
            return False

    def execute_template_process(self):
        run(self.template_creator_cmd_line())
        for path in [self.path_to_classes_file, self.path_to_out_template]:
            if path:
                with open(path) as f:
                    assert f.read(), "{0} is empty".format(path)

    def execute_grabber_process(self):
        p = Popen(self.grabber_cmd_line())
        assert p.poll() is None
        assert self.check_if_grabber_is_on()

    def stop_grabber(self):
        def make_nice_trace(t):
            return list(
                map(lambda x: x.lower().replace("java.lang.", "").replace("java.io.", "").replace("java.util.", ""), t))

        Popen(["java", "-jar", Tracer.JCOV_JAR_PATH, "grabberManager", "-save", '-command_port',
               str(self.command_port)]).communicate()
        Popen(["java", "-jar", Tracer.JCOV_JAR_PATH, "grabberManager", "-stop", '-command_port',
               str(self.command_port)]).communicate()
        traces = list(JcovParser(None, [self.path_to_result_file], True, True).parse(False))[0].split_to_subtraces()
        trigger_tests = list(map(lambda x: x.lower(), self.get_trigger_tests()))
        relevant_traces = traces
        tests_details = []
        for t in relevant_traces:
            if traces[t].get_trace():
                tests_details.append((t, traces[t].get_trace(), 1 if t.lower().split('(')[0] in trigger_tests else 0))
        tests_names = set(list(map(lambda x: x[0], tests_details)) + list(map(lambda x: x[0].lower(), tests_details)))
        fail_components = reduce(set.__or__, list(map(lambda x: set(x[1]), filter(lambda x: x[2] == 1, tests_details))),
                                 set())
        all_components = reduce(set.__or__, list(map(lambda x: set(x[1]), tests_details)), set())
        fail_components = set(
            filter(lambda x: not x.lower().split('.')[-2].endswith('test'), fail_components - tests_names))
        optimized_tests = list(filter(lambda x: x[1],
                                      map(lambda x: (x[0], make_nice_trace(list(set(x[1]) & fail_components)), x[2]),
                                          tests_details)))
        components = reduce(set.__or__, list(map(lambda x: set(x[1]), optimized_tests)), set())
        bugs = []
        with open(self.bugs_file) as f:
            bugs_all_comps = list(set(map(lambda x: x.lower(), set(json.loads(f.read())))) & all_components)
            bugs = list(set(bugs_all_comps) & components)
        with open(self.path_to_tests_details, "w") as f:
            json.dump(optimized_tests, f)
        with open(self.path_to_tests_details + '2', "w") as f:
            json.dump(tests_details, f)
        if bugs_all_comps:
            write_json_planning_file(self.matrix, optimized_tests, bugs)

    def get_xml_files(self):
        for root, _, files in os.walk(os.path.dirname(self.xml_path)):
            for name in files:
                if name.endswith('.xml'):
                    yield os.path.join(root, name)

    def observe_tests(self):
        self.test_results = {}
        for report in self.get_xml_files():
            try:
                suite = JUnitXml.fromfile(report)
                for case in suite:
                    test = TestResult(case, suite.name, report)
                    self.test_results[test.full_name.lower()] = test
            except Exception as e:
                print(e, report)
                pass
        with open(self.path_to_tests_results, "w") as f:
            json.dump(list(map(lambda x: x.as_dict(), self.test_results.values())), f)
        tests = list(set(map(lambda x: x.full_name, filter(lambda t: not t.is_passed(), self.test_results.values()))))
        with open(self.trigger_tests_path, 'w') as f:
            json.dump(tests, f)
        if not os.path.exists(self.tests_to_exclude_path):
            with open(self.tests_to_exclude_path, 'w') as f:
                json.dump(tests, f)
        return self.test_results

    def get_trigger_tests(self):
        with open(self.trigger_tests_path) as f:
            exclude = json.loads(f.read())
            return exclude

    def get_buggy_functions(self):
        bugs = list(set(map(lambda x: x.method_name_parameters.replace(',', ';'),
                            diff.get_modified_exists_functions(os.path.dirname(self.xml_path)))))
        if bugs:
            with open(self.bugs_file, "w") as f:
                json.dump(bugs, f)

    def create_call_graph(self, jar_path):
        cmd = ["java", "-jar", Tracer.CALL_GRAPH_JAR_PATH, jar_path]
        edges = set()
        edges = edges.union(set(
            str(Popen(cmd, stdout=PIPE).communicate()[0]).replace('(M)', '').replace('(I)', '').replace('(D)',
                                                                                                        '').replace(
                '(S)', '').replace('(O)', '').replace('\\r', '').split('\\n')))
        classes_edges = set()
        for v, u in list(filter(lambda x: x, map(lambda x: x[2:].split(), edges))):
            if ':' in v:
                v = v.split(':')[0]
            if ':' in u:
                u = u.split(':')[0]
            if '$' in v:
                v = v.split('$')[0]
            if '$' in u:
                u = u.split('$')[0]
            if v.startswith('['):
                v = v[2:]
            if u.startswith('['):
                u = u[2:]
            if '[' in v:
                v = v.split('[')[0]
            if '[' in u:
                u = u.split('[')[0]
            for prefix in ['java.', 'org.junit', 'javax.']:
                if u.startswith(prefix) or v.startswith(prefix):
                    u = ''
                    v = ''
            if v != u and v and u:
                classes_edges.add((v, u))
        g_forward = nx.DiGraph()
        g_forward.add_edges_from(classes_edges)
        nx.write_gexf(g_forward, self.call_graph_path)
        bugs_classes = []
        with open(self.bugs_file) as f:
            bugs_classes = list(set(map(lambda x: '.'.join(x.split('.')[:-1]), json.loads(f.read()))))
        trigger_tests_classes = list(set(map(lambda x: '.'.join(x.split('.')[:-1]), self.get_trigger_tests())))
        tests_classes = list(filter(
            lambda x: x.split('.')[-1].startswith('Test') or x.split('.')[-1].endswith('Test') or x.split('.')[
                -1].endswith('TestCase'), g_forward.nodes))
        relevant_tests = set()
        for t in tests_classes:
            for b in bugs_classes:
                if t not in g_forward or b not in g_forward:
                    continue
                if nx.has_path(g_forward, t, b):
                    relevant_tests.add(t)
                    break
        if not set(trigger_tests_classes).intersection(relevant_tests):
            return
        g2 = nx.DiGraph(g_forward)
        nx.write_gexf(g2, self.call_graph_path + '2')
        relevant_nodes = set(relevant_tests)
        relevant_nodes.update(set(bugs_classes))
        for t in relevant_tests:
            if t not in g2:
                continue
            paths = nx.single_source_shortest_path(g2, t)
            reachable = set(paths.keys())
            relevant_nodes.update(reachable)
            g2.remove_nodes_from(reachable)
        with open(self.call_graph_tests_path, "w") as f:
            json.dump(list(relevant_tests), f)
        with open(self.call_graph_nodes_path, "w") as f:
            json.dump(list(relevant_nodes), f)

    def triple(self):
        self.set_junit_formatter()
        self.execute_template_process()
        self.execute_grabber_process()


if __name__ == '__main__':
    t = Tracer(os.path.abspath(sys.argv[1]), sys.argv[2])
    if sys.argv[-1] == 'template':
        t.execute_template_process()
    elif sys.argv[-1] == 'grabber':
        t.execute_grabber_process()
    elif sys.argv[-1] == 'formatter':
        t.set_junit_formatter()
    elif sys.argv[-1] == 'triple':
        t.set_junit_formatter()
        t.execute_template_process()
        t.execute_grabber_process()
    elif sys.argv[-1] == 'properties':
        t.set_junit_props()
    elif sys.argv[-1] == 'get_buggy_functions':
        t.get_buggy_functions()
    elif sys.argv[-1] == 'call_graph':
        t.create_call_graph()
    elif sys.argv[-1] == 'collect_failed_tests':
        t.observe_tests()
    elif sys.argv[-1] == 'exclude_tests':
        t.exclude_tests()
    else:
        t.stop_grabber()
