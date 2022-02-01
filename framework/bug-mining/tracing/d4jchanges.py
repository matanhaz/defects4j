import sys
from xml.dom.minidom import parse
import os
import xml.etree.cElementTree as et
from functools import reduce
et.register_namespace('', "http://maven.apache.org/POM/4.0.0")
et.register_namespace('xsi', "http://www.w3.org/2001/XMLSchema-instance")


class Pom(object):
    def __init__(self, pom_path):
        self.pom_path = pom_path
        self.element_tree = et.parse(self.pom_path)

    @staticmethod
    def get_children_by_name(element, name):
        return list(filter(lambda e: e.tag.endswith(name), element.getchildren()))


    def remove_elements_by_path(self, path):
        elements = [self.element_tree.getroot()]
        for name in path[:-1]:
            elements = reduce(list.__add__, list(map(lambda elem: Pom.get_children_by_name(elem, name), elements)), [])
        for element in elements:
            for child in element.getchildren():
                if child.tag.endswith(path[-1]):
                    element.remove(child)

    def remove_compiler_version(self, version='1.8'):
        for p in ['maven.compile.source', 'maven.compile.target']:
            self.remove_elements_by_path(['properties', p])
        for e in ['source', 'target']:
            self.remove_elements_by_path(['build', 'plugins', 'plugin'] + ["maven-compiler-plugin", "configuration", e])
        self.save()


    def save(self):
        self.element_tree.write(self.pom_path, xml_declaration=True)


class SourceFixer(object):
    def __init__(self, repo_dir):
        self._repo_dir = repo_dir
        self.DEFAULT_ES_VERSION = '1.0.6'
        self.DEFAULT_SUREFIRE_VERSION = '2.17'
        self.DEFAULT_JUNIT_VERSION = '4.12'
        self.DEFAULT_XERCES_VERSION = '2.11.0'
        self.MAVEN_COMPILER_SOURCE = None
        self.build_report = None
        self.traces = None

    # Changes all the pom files in a module recursively
    def get_all_pom_paths(self, module=None):
        ans = []
        inspected_module = self._repo_dir
        if module is not None:
            inspected_module = module
        pom_path = os.path.join(inspected_module, 'pom.xml')
        if os.path.isfile(pom_path):
            try:
                parse(pom_path)
                ans.append(pom_path)
            except:
                pass
        for file in os.listdir(inspected_module):
            full_path = os.path.join(inspected_module, file)
            if os.path.isdir(full_path):
                ans.extend(self.get_all_pom_paths(full_path))
        return ans

    def remove_compiler_version(self):
        for pom_file in self.get_all_pom_paths(self._repo_dir):
            pom = Pom(pom_file)
            pom.remove_compiler_version()
