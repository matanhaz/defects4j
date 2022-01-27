import sys
from xml.dom.minidom import parse
from pom_file import Pom
import os

class Repo(object):

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

    def set_compiler_version(self, version='1.7'):
        for pom_file in self.get_all_pom_paths(self._repo_dir):
            pom = Pom(pom_file)
            pom.set_compiler_version(version=version)


if __name__ == '__main__':
    repo = Repo(sys.argv[1])
    repo.set_compiler_version(sys.argv[2])