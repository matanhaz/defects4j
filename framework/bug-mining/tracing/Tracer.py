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

    def is_passed(self):
        return self.outcome == 'pass'

    def get_observation(self):
        return 0 if self.is_passed() else 1

    def as_dict(self):
        return {'_test_name': self.full_name, '_outcome': self.outcome}


class Tracer:
    JCOV_JAR_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "externals", "jcov.jar")
    path_to_classes_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "externals", "classes")
    path_to_out_template = os.path.join(os.path.dirname(os.path.realpath(__file__)), "externals", "template.xml")

    def __init__(self, xml_path):
        self.classes_dir = None
        self.command_port = 5552
        self.agent_port = 5551
        self.xml_path = xml_path
        p = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        bug_mining = os.path.join(p, list(filter(lambda x: x.startswith('bug-mining'), os.listdir(p)))[0], 'framework', 'projects')
        self.path_to_result_file = os.path.abspath(os.path.join(bug_mining, os.listdir(bug_mining)[0], "result.xml"))
        self.path_to_tests_details = os.path.abspath(os.path.join(bug_mining, os.listdir(bug_mining)[0], "test_details.json"))
        self.test_results = {}

    def set_junit_formatter(self):
        print('set_junit_formatter')
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
                    JCOV_JAR_PATH=Tracer.JCOV_JAR_PATH, PORT=self.agent_port, CLASSES_FILE=Tracer.path_to_classes_file, OUT_TEMPLATE=Tracer.path_to_out_template)
                jvmarg.attrib.update({'value': arg_line})
        element_tree.write(self.xml_path, xml_declaration=True)

    def get_classes_path(self):
        all_classes = {os.path.dirname(self.xml_path)}
        for root, dirs, files in os.walk(os.path.dirname(self.xml_path)):
            for f in files:
                if f.endswith('class'):
                    all_classes.add(root)
                    break
        print(all_classes)
        return all_classes

    def template_creator_cmd_line(self):
        cmd_line = ["java", '-Xms2g', '-jar', Tracer.JCOV_JAR_PATH, 'tmplgen', '-verbose', '-t', Tracer.path_to_out_template, '-c', Tracer.path_to_classes_file, '-type', 'method']
        cmd_line.extend(self.get_classes_path())
        return cmd_line

    def grabber_cmd_line(self):
            cmd_line = ["java", '-Xms2g', '-jar', Tracer.JCOV_JAR_PATH, 'grabber', '-vv', '-port', self.agent_port, '-command_port', self.command_port, '-t', Tracer.path_to_out_template, '-o', self.path_to_result_file]
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

    def execute_jcov_process(self):
        print(self.template_creator_cmd_line())
        run(self.template_creator_cmd_line())
        for path in [self.path_to_classes_file, self.path_to_out_template]:
            if path:
                with open(path) as f:
                    assert f.read(), "{0} is empty".format(path)
        print(self.grabber_cmd_line())
        p = Popen(self.grabber_cmd_line())
        assert p.poll() is None
        assert self.check_if_grabber_is_on()

    def stop_grabber(self):
        Popen(["java", "-jar", Tracer.JCOV_JAR_PATH, "grabberManager", "-save", '-command_port', str(self.command_port)]).communicate()
        Popen(["java", "-jar", Tracer.JCOV_JAR_PATH, "grabberManager", "-stop", '-command_port', str(self.command_port)]).communicate()
        traces = list(JcovParser(os.path.dirname(self.path_to_result_file), True, True).parse(False))[0].split_to_subtraces()
        self.observe_tests()
        relevant_traces = list(filter(lambda t: t.split('(')[0].lower() in self.test_results, traces))
        tests_details = []
        for t in relevant_traces:
            tests_details.append((t, traces[t].get_trace(), 0 if self.test_results[t.split('(')[0].lower()].outcome == 'pass' else 1))
        with open(self.path_to_tests_details, "w") as f:
            json.dump(tests_details, f)

    def get_xml_files(self):
        for root, _, files in os.walk(os.path.dirname(self.xml_path)):
            for name in files:
                if name.endswith('.xml'):
                    yield os.path.join(root, name)

    def observe_tests(self, save_to=None):
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
        if save_to:
            with open(save_to, "w") as f:
                json.dump(list(map(lambda x: self.test_results[x].as_dict(), self.test_results)), f)
        return self.test_results


if __name__ == '__main__':
    t = Tracer(os.path.join(os.path.abspath(sys.argv[1]), 'build.xml'))
    print(t.__dict__)
    if len(sys.argv) == 3:
        if sys.argv[-1] == 'start':
            t.execute_jcov_process()
        elif sys.argv[-1] == 'formatter':
            t.set_junit_formatter()
        else:
            t.stop_grabber()

