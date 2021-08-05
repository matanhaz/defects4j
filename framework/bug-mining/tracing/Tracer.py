import xml.etree.cElementTree as et
import os
import sys
import socket
import json
from junitparser.junitparser import Error, Failure, Skipped
from junitparser import JUnitXml
from subprocess import Popen, PIPE, run
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
import git
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

    def __init__(self, xml_path, bug_mining=None):
        self.classes_dir = None
        self.command_port = 5552
        self.agent_port = 5551
        self.xml_path = xml_path
        p = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        ind = 0
        if bug_mining is None:
            ind = list(filter(lambda x: x.startswith('bug-mining'), os.listdir(p)))[0].split('_')[1]
            bug_mining = os.path.join(p, list(filter(lambda x: x.startswith('bug-mining'), os.listdir(p)))[0], 'framework', 'projects')
        self.path_to_result_file = os.path.abspath(os.path.join(bug_mining, os.listdir(bug_mining)[0], "result.xml"))
        self.path_to_out_template = os.path.abspath(os.path.join(bug_mining, os.listdir(bug_mining)[0], "template.xml"))
        self.path_to_classes_file = os.path.abspath(os.path.join(bug_mining, os.listdir(bug_mining)[0], "classes"))
        self.path_to_tests_details = os.path.abspath(os.path.join(bug_mining, os.listdir(bug_mining)[0], "test_details.json"))
        self.path_to_tests_results = os.path.abspath(os.path.join(bug_mining, os.listdir(bug_mining)[0], "test_results.json"))
        trigger_tests = os.path.abspath(os.path.join(bug_mining, os.listdir(bug_mining)[0], "trigger_tests"))
        self.path_to_trigger_tests = os.path.join(trigger_tests, os.listdir(trigger_tests)[0])
        self.buggy_functions = os.path.abspath(os.path.join(bug_mining, os.listdir(bug_mining)[0], "buggy_functions.json"))
        self.matrix = os.path.abspath(os.path.join(bug_mining, os.listdir(bug_mining)[0], f"matrix_{ind}.json"))
        self.test_results = {}

    def set_junit_formatter(self):
        element_tree = et.parse(self.xml_path)
        junit = list(filter(lambda x: x.tag == 'junit', element_tree.iter()))
        if junit:
            for j in junit:
                j.attrib.update({'fork': 'yes'})
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
                    JCOV_JAR_PATH=Tracer.JCOV_JAR_PATH, PORT=self.agent_port, CLASSES_FILE=self.path_to_classes_file, OUT_TEMPLATE=self.path_to_out_template)
                jvmarg.attrib.update({'value': arg_line})
        element_tree.write(self.xml_path, xml_declaration=True)

    def get_classes_path(self):
        all_classes = {os.path.dirname(self.xml_path)}
        for root, dirs, files in os.walk(os.path.dirname(self.xml_path)):
            for f in files:
                if f.endswith('class'):
                    all_classes.add(root)
                    break
        return all_classes

    def template_creator_cmd_line(self):
        cmd_line = ["java", '-Xms2g', '-jar', Tracer.JCOV_JAR_PATH, 'tmplgen', '-verbose', '-t', self.path_to_out_template, '-c', self.path_to_classes_file, '-type', 'method']
        cmd_line.extend(self.get_classes_path())
        return cmd_line

    def grabber_cmd_line(self):
            cmd_line = ["java", '-Xms2g', '-jar', Tracer.JCOV_JAR_PATH, 'grabber', '-vv', '-port', self.agent_port, '-command_port', self.command_port, '-t', self.path_to_out_template, '-o', self.path_to_result_file]
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

    def stop_grabber(self, bugs_file):
        def make_nice_trace(t):
            return list(map(lambda x: x.lower().replace("java.lang.", "").replace("java.io.", "").replace("java.util.", ""), t))

        def get_obs(t):
            if self.test_results.get(t.split('(')[0].lower()):
                return self.test_results[t.split('(')[0].lower()].get_observation()
            return 0

        Popen(["java", "-jar", Tracer.JCOV_JAR_PATH, "grabberManager", "-save", '-command_port', str(self.command_port)]).communicate()
        Popen(["java", "-jar", Tracer.JCOV_JAR_PATH, "grabberManager", "-stop", '-command_port', str(self.command_port)]).communicate()
        traces = list(JcovParser(None, [self.path_to_result_file], True, True).parse(False))[0].split_to_subtraces()
        print(traces.keys())
        self.observe_tests()
        # relevant_traces = list(filter(lambda t: t.split('(')[0].lower() in self.test_results, traces))
        relevant_traces = traces
        tests_details = []
        for t in relevant_traces:
            if traces[t].get_trace():
                tests_details.append((t, traces[t].get_trace(), get_obs(t)))
                # tests_details.append((t, traces[t].get_trace(), self.test_results[t.split('(')[0].lower()].get_observation()))
        tests_names = set(list(map(lambda x: x[0], tests_details)) + list(map(lambda x: x[0].lower(), tests_details)))
        fail_components = reduce(set.__or__, list(map(lambda x: set(x[1]), filter(lambda x: x[2] == 1, tests_details))), set())
        fail_components = fail_components - tests_names
        optimized_tests = list(filter(lambda x: x[1], map(lambda x: (x[0], make_nice_trace(list(set(x[1]) & fail_components)), x[2]), tests_details)))
        components = reduce(set.__or__, list(map(lambda x: set(x[1]), optimized_tests)), set())
        bugs = []
        with open(bugs_file) as f:
            bugs = list(set(json.loads(f.read())) - components)
        with open(self.path_to_tests_details, "w") as f:
            json.dump(optimized_tests, f)
        with open(self.path_to_tests_details + '2', "w") as f:
            json.dump(tests_details, f)
        write_json_planning_file(self.matrix, optimized_tests, bugs)

    def get_xml_files(self):
        for root, _, files in os.walk(os.path.dirname(self.xml_path)):
            for name in files:
                if name.endswith('.xml'):
                    yield os.path.join(root, name)

    def observe_tests(self):
        self.test_results = {}
        with open(self.path_to_trigger_tests) as f:
            trigger_tests = list(map(lambda x: x[4:-1].replace('::', '.').lower(), filter(lambda l: l.startswith('---'), f.readlines())))
        for report in self.get_xml_files():
            try:
                suite = JUnitXml.fromfile(report)
                for case in suite:
                    test = TestResult(case, suite.name, report)
                    test.set_failure(test.full_name.lower() in trigger_tests)
                    self.test_results[test.full_name.lower()] = test
            except Exception as e:
                print(e, report)
                pass
        with open(self.path_to_tests_results, "w") as f:
            json.dump(list(map(lambda x: x.as_dict(), self.test_results.values())), f)
        return self.test_results

    def get_buggy_functions(self, patch_file, save_to):
        repo = git.Repo(os.path.dirname(self.xml_path))
        if os.path.exists(patch_file):
            repo.git.apply(patch_file)
        with open(save_to, "w") as f:
            json.dump(list(set(map(lambda x: x.method_name_parameters.lower().replace(',', ';'), diff.get_modified_exists_functions(os.path.dirname(self.xml_path))))), f)


if __name__ == '__main__':
    t = Tracer(os.path.join(os.path.abspath(sys.argv[1]), 'build.xml'))
    # t = Tracer(os.path.join(os.path.abspath(sys.argv[1]), 'build.xml'), r'C:\Users\amirelm\Downloads\bug-mining (13)\bug-mining_32\framework\projects')
    # t.stop_grabber(r"C:\Users\amirelm\Downloads\bug-mining (13)\bug-mining_32\framework\projects\Lang\bugs.json")
    if sys.argv[-1] == 'template':
        t.execute_template_process()
    elif sys.argv[-1] == 'grabber':
        t.execute_grabber_process()
    elif sys.argv[-1] == 'formatter':
        t.set_junit_formatter()
    elif sys.argv[-1] == 'patch':
        t.get_buggy_functions(sys.argv[2], sys.argv[3])
    else:
        t.stop_grabber(sys.argv[2])

