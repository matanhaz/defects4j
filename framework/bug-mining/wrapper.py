import os
import sys
from functools import reduce
from subprocess import run
from issues_extractor import extract_issues
import json
import os
import re
import time
from datetime import datetime

import git
import jira
import pandas as pd
from pydriller import Repository
from subprocess import Popen, PIPE, run
from d4jchanges import SourceFixer

projects = {'distributedlog': ('https://github.com/apache/distributedlog', 'DL'),
            'maven-indexer': ('https://github.com/apache/maven-indexer', 'MINDEXER'),
            'rampart': ('https://github.com/apache/rampart', 'RAMPART'),
            'commons-functor': ('https://github.com/apache/commons-functor', 'FUNCTOR'),
            'velocity-tools': ('https://github.com/apache/velocity-tools', 'VELTOOLS'),
            'commons-fileupload': ('https://github.com/apache/commons-fileupload',
                                   'FILEUPLOAD'),
            'crunch': ('https://github.com/apache/crunch', 'CRUNCH'),
            'johnzon': ('https://github.com/apache/johnzon', 'JOHNZON'),
            'joshua': ('https://github.com/apache/joshua', 'JOSHUA'),
            'marmotta': ('https://github.com/apache/marmotta', 'MARMOTTA'),
            'qpid': ('https://github.com/apache/qpid', 'QPID'),
            'mnemonic': ('https://github.com/apache/mnemonic', 'MNEMONIC'),
            'james-jdkim': ('https://github.com/apache/james-jdkim', 'JDKIM'),
            'maven-patch-plugin': ('https://github.com/apache/maven-patch-plugin',
                                   'MPATCH'),
            'commons-dbcp': ('https://github.com/apache/commons-dbcp', 'DBCP'),
            'commons-crypto': ('https://github.com/apache/commons-crypto', 'CRYPTO'),
            'commons-jexl': ('https://github.com/apache/commons-jexl', 'JEXL'),
            'curator': ('https://github.com/apache/curator', 'CURATOR'),
            'maven-wagon': ('https://github.com/apache/maven-wagon', 'WAGON'),
            'maven-jlink-plugin': ('https://github.com/apache/maven-jlink-plugin',
                                   'MJLINK'),
            'commons-weaver': ('https://github.com/apache/commons-weaver', 'WEAVER'),
            'qpid-jms': ('https://github.com/apache/qpid-jms', 'QPIDJMS'),
            'pulsar': ('https://github.com/apache/pulsar', 'PULSAR'),
            'directmemory': ('https://github.com/apache/directmemory', 'DIRECTMEMORY'),
            'nifi': ('https://github.com/apache/nifi', 'NIFI'),
            'commons-email': ('https://github.com/apache/commons-email', 'EMAIL'),
            'activemq-openwire': ('https://github.com/apache/activemq-openwire',
                                  'OPENWIRE'),
            'maven-javadoc-plugin': ('https://github.com/apache/maven-javadoc-plugin',
                                     'MJAVADOC'),
            'mina': ('https://github.com/apache/mina', 'DIRMINA'),
            'juneau': ('https://github.com/apache/juneau', 'JUNEAU'),
            'maven-resolver': ('https://github.com/apache/maven-resolver', 'MRESOLVER'),
            'jackrabbit-oak': ('https://github.com/apache/jackrabbit-oak', 'OAK'),
            'commons-validator': ('https://github.com/apache/commons-validator',
                                  'VALIDATOR'),
            'james-jspf': ('https://github.com/apache/james-jspf', 'JSPF'),
            'tiles': ('https://github.com/apache/tiles', 'TILES'),
            'maven-dependency-plugin': ('https://github.com/apache/maven-dependency-plugin',
                                        'MDEP'),
            'zookeeper': ('https://github.com/apache/zookeeper', 'ZOOKEEPER'),
            'airavata': ('https://github.com/apache/airavata', 'AIRAVATA'),
            'maven-rar-plugin': ('https://github.com/apache/maven-rar-plugin', 'MRAR'),
            'rocketmq': ('https://github.com/apache/rocketmq', 'ROCKETMQ'),
            'openejb': ('https://github.com/apache/openejb', 'OPENEJB'),
            'submarine': ('https://github.com/apache/submarine', 'SUBMARINE'),
            'stanbol': ('https://github.com/apache/stanbol', 'STANBOL'),
            'nifi-registry': ('https://github.com/apache/nifi-registry', 'NIFIREG'),
            'maven-remote-resources-plugin': ('https://github.com/apache/maven-remote-resources-plugin',
                                              'MRRESOURCES'),
            'hadoop-common': ('https://github.com/apache/hadoop-common', 'HADOOP'),
            'openjpa': ('https://github.com/apache/openjpa', 'OPENJPA'),
            'syncope': ('https://github.com/apache/syncope', 'SYNCOPE'),
            'servicemix': ('https://github.com/apache/servicemix', 'SM'),
            'phoenix-omid': ('https://github.com/apache/phoenix-omid', 'OMID'),
            'phoenix-tephra': ('https://github.com/apache/phoenix-tephra', 'TEPHRA'),
            'myfaces-trinidad': ('https://github.com/apache/myfaces-trinidad',
                                 'TRINIDAD'),
            'jena': ('https://github.com/apache/jena', 'JENA'),
            'commons-logging': ('https://github.com/apache/commons-logging', 'LOGGING'),
            'maven-pdf-plugin': ('https://github.com/apache/maven-pdf-plugin', 'MPDF'),
            'maven-archetype': ('https://github.com/apache/maven-archetype', 'ARCHETYPE'),
            'hama': ('https://github.com/apache/hama', 'HAMA'),
            'archiva': ('https://github.com/apache/archiva', 'MRM'),
            'commons-pool': ('https://github.com/apache/commons-pool', 'POOL'),
            'plc4x': ('https://github.com/apache/plc4x', 'PLC4X'),
            'oltu': ('https://github.com/apache/oltu', 'OLTU'),
            'ftpserver': ('https://github.com/apache/ftpserver', 'FTPSERVER'),
            'cloudstack': ('https://github.com/apache/cloudstack', 'CLOUDSTACK'),
            'maven-verifier-plugin': ('https://github.com/apache/maven-verifier-plugin',
                                      'MVERIFIER'),
            'metron': ('https://github.com/apache/metron', 'METRON'),
            'wicket': ('https://github.com/apache/wicket', 'WICKET'),
            'aries': ('https://github.com/apache/aries', 'ARIES'),
            'accumulo': ('https://github.com/apache/accumulo', 'ACCUMULO'),
            'maven-shade-plugin': ('https://github.com/apache/maven-shade-plugin',
                                   'MSHADE'),
            'unomi': ('https://github.com/apache/unomi', 'UNOMI'),
            'maven-gpg-plugin': ('https://github.com/apache/maven-gpg-plugin', 'MGPG'),
            'maven-toolchains-plugin': ('https://github.com/apache/maven-toolchains-plugin',
                                        'MTOOLCHAINS'),
            'maven-jdeprscan-plugin': ('https://github.com/apache/maven-jdeprscan-plugin',
                                       'MJDEPRSCAN'),
            'flink': ('https://github.com/apache/flink', 'FLINK'),
            'commons-lang': ('https://github.com/apache/commons-lang', 'LANG'),
            'mahout': ('https://github.com/apache/mahout', 'MAHOUT'),
            'metamodel': ('https://github.com/apache/metamodel', 'METAMODEL'),
            'eagle': ('https://github.com/apache/eagle', 'EAGLE'),
            'maven-help-plugin': ('https://github.com/apache/maven-help-plugin', 'MPH'),
            'tika': ('https://github.com/apache/tika', 'TIKA'),
            'ambari': ('https://github.com/apache/ambari', 'AMBARI'),
            'vxquery': ('https://github.com/apache/vxquery', 'VXQUERY'),
            'maven-jdeps-plugin': ('https://github.com/apache/maven-jdeps-plugin',
                                   'MJDEPS'),
            'commons-rng': ('https://github.com/apache/commons-rng', 'RNG'),
            'helix': ('https://github.com/apache/helix', 'HELIX'),
            'tinkerpop': ('https://github.com/apache/tinkerpop', 'TINKERPOP'),
            'isis': ('https://github.com/apache/isis', 'ISIS'),
            'synapse': ('https://github.com/apache/synapse', 'SYNAPSE'),
            'hcatalog': ('https://github.com/apache/hcatalog', 'HCATALOG'),
            'asterixdb': ('https://github.com/apache/asterixdb', 'ASTERIXDB'),
            'commons-proxy': ('https://github.com/apache/commons-proxy', 'PROXY'),
            'sandesha': ('https://github.com/apache/sandesha', 'SAND'),
            'shindig': ('https://github.com/apache/shindig', 'SHINDIG'),
            'commons-imaging': ('https://github.com/apache/commons-imaging', 'IMAGING'),
            'openwebbeans': ('https://github.com/apache/openwebbeans', 'OWB'),
            'maven-plugin-testing': ('https://github.com/apache/maven-plugin-testing',
                                     'MPLUGINTESTING'),
            'tomee': ('https://github.com/apache/tomee', 'TOMEE'),
            'activemq-cli-tools': ('https://github.com/apache/activemq-cli-tools',
                                   'AMQCLI'),
            'geronimo': ('https://github.com/apache/geronimo', 'GERONIMO'),
            'juddi': ('https://github.com/apache/juddi', 'JUDDI'),
            'maven-project-info-reports-plugin': ('https://github.com/apache/maven-project-info-reports-plugin',
                                                  'MPIR'),
            'commons-net': ('https://github.com/apache/commons-net', 'NET'),
            'odftoolkit': ('https://github.com/apache/odftoolkit', 'ODFTOOLKIT'),
            'maven-changelog-plugin': ('https://github.com/apache/maven-changelog-plugin',
                                       'MCHANGELOG'),
            'bval': ('https://github.com/apache/bval', 'BVAL'),
            'cayenne': ('https://github.com/apache/cayenne', 'CAY'),
            'chainsaw': ('https://github.com/apache/chainsaw', 'CHAINSAW'),
            'cxf-fediz': ('https://github.com/apache/cxf-fediz', 'FEDIZ'),
            'commons-beanutils': ('https://github.com/apache/commons-beanutils',
                                  'BEANUTILS'),
            'commons-ognl': ('https://github.com/apache/commons-ognl', 'OGNL'),
            'tajo': ('https://github.com/apache/tajo', 'TAJO'),
            'cxf': ('https://github.com/apache/cxf', 'CXF'),
            'james-jsieve': ('https://github.com/apache/james-jsieve', 'JSIEVE'),
            'phoenix': ('https://github.com/apache/phoenix', 'PHOENIX'),
            'pivot': ('https://github.com/apache/pivot', 'PIVOT'),
            'maven-resources-plugin': ('https://github.com/apache/maven-resources-plugin',
                                       'MRESOURCES'),
            'gora': ('https://github.com/apache/gora', 'GORA'),
            'commons-io': ('https://github.com/apache/commons-io', 'IO'),
            'activemq': ('https://github.com/apache/activemq', 'AMQ'),
            'maven-jar-plugin': ('https://github.com/apache/maven-jar-plugin', 'MJAR'),
            'commons-collections': ('https://github.com/apache/commons-collections',
                                    'COLLECTIONS'),
            'manifoldcf': ('https://github.com/apache/manifoldcf', 'CONNECTORS'),
            'griffin': ('https://github.com/apache/griffin', 'GRIFFIN'),
            'chukwa': ('https://github.com/apache/chukwa', 'CHUKWA'),
            'oodt': ('https://github.com/apache/oodt', 'OODT'),
            'kalumet': ('https://github.com/apache/kalumet', 'KALUMET'),
            'tez': ('https://github.com/apache/tez', 'TEZ'),
            'maven-ejb-plugin': ('https://github.com/apache/maven-ejb-plugin', 'MEJB'),
            'deltaspike': ('https://github.com/apache/deltaspike', 'DELTASPIKE'),
            'commons-jelly': ('https://github.com/apache/commons-jelly', 'JELLY'),
            'jclouds': ('https://github.com/apache/jclouds', 'JCLOUDS'),
            'ranger': ('https://github.com/apache/ranger', 'RANGER'),
            'activemq-artemis': ('https://github.com/apache/activemq-artemis', 'ARTEMIS'),
            'sentry': ('https://github.com/apache/sentry', 'SENTRY'),
            'activemq-apollo': ('https://github.com/apache/activemq-apollo', 'APLO'),
            'rya': ('https://github.com/apache/rya', 'RYA'),
            'commons-codec': ('https://github.com/apache/commons-codec', 'CODEC'),
            'ddlutils': ('https://github.com/apache/ddlutils', 'DDLUTILS'),
            'commons-text': ('https://github.com/apache/commons-text', 'TEXT'),
            'giraph': ('https://github.com/apache/giraph', 'GIRAPH'),
            'bigtop': ('https://github.com/apache/bigtop', 'BIGTOP'),
            'commons-configuration': ('https://github.com/apache/commons-configuration',
                                      'CONFIGURATION'),
            'james-mime4j': ('https://github.com/apache/james-mime4j', 'MIME4J'),
            'maven-site-plugin': ('https://github.com/apache/maven-site-plugin', 'MSITE'),
            'opennlp': ('https://github.com/apache/opennlp', 'OPENNLP'),
            'storm': ('https://github.com/apache/storm', 'STORM'),
            'zeppelin': ('https://github.com/apache/zeppelin', 'ZEPPELIN'),
            'maven-doap-plugin': ('https://github.com/apache/maven-doap-plugin', 'MDOAP'),
            'maven-changes-plugin': ('https://github.com/apache/maven-changes-plugin',
                                     'MCHANGES'),
            'maven-doxia': ('https://github.com/apache/maven-doxia', 'DOXIA'),
            'maven-surefire': ('https://github.com/apache/maven-surefire', 'SUREFIRE'),
            'myfaces-test': ('https://github.com/apache/myfaces-test', 'MYFACESTEST'),
            'twill': ('https://github.com/apache/twill', 'TWILL'),
            'continuum': ('https://github.com/apache/continuum', 'CONTINUUM'),
            'maven-clean-plugin': ('https://github.com/apache/maven-clean-plugin',
                                   'MCLEAN'),
            'kylin': ('https://github.com/apache/kylin', 'KYLIN'),
            'maven-doxia-tools': ('https://github.com/apache/maven-doxia-tools',
                                  'DOXIATOOLS'),
            'jsecurity': ('https://github.com/apache/jsecurity', 'JSEC'),
            'maven-deploy-plugin': ('https://github.com/apache/maven-deploy-plugin',
                                    'MDEPLOY'),
            'tiles-autotag': ('https://github.com/apache/tiles-autotag', 'AUTOTAG'),
            'mina-sshd': ('https://github.com/apache/mina-sshd', 'SSHD'),
            'maven-compiler-plugin': ('https://github.com/apache/maven-compiler-plugin',
                                      'MCOMPILER'),
            'maven-install-plugin': ('https://github.com/apache/maven-install-plugin',
                                     'MINSTALL'),
            'sanselan': ('https://github.com/apache/sanselan', 'SANSELAN'),
            'avro': ('https://github.com/apache/avro', 'AVRO'),
            'commons-compress': ('https://github.com/apache/commons-compress',
                                 'COMPRESS'),
            'hadoop': ('https://github.com/apache/hadoop', 'HADOOP'),
            'shiro': ('https://github.com/apache/shiro', 'SHIRO'),
            'empire-db': ('https://github.com/apache/empire-db', 'EMPIREDB'),
            'commons-bsf': ('https://github.com/apache/commons-bsf', 'BSF'),
            'chemistry': ('https://github.com/apache/chemistry', 'CMIS'),
            'commons-digester': ('https://github.com/apache/commons-digester',
                                 'DIGESTER'),
            'directory-studio': ('https://github.com/apache/directory-studio',
                                 'DIRSTUDIO'),
            'falcon': ('https://github.com/apache/falcon', 'FALCON'),
            'myfaces-tobago': ('https://github.com/apache/myfaces-tobago', 'TOBAGO'),
            'maven-assembly-plugin': ('https://github.com/apache/maven-assembly-plugin',
                                      'MASSEMBLY'),
            'openmeetings': ('https://github.com/apache/openmeetings', 'OPENMEETINGS'),
            'savan': ('https://github.com/apache/savan', 'SAVAN'),
            'maven-invoker-plugin': ('https://github.com/apache/maven-invoker-plugin',
                                     'MINVOKER'),
            'pdfbox': ('https://github.com/apache/pdfbox', 'PDFBOX'),
            'maven-jxr': ('https://github.com/apache/maven-jxr', 'JXR'),
            'reef': ('https://github.com/apache/reef', 'REEF'),
            'maven-checkstyle-plugin': ('https://github.com/apache/maven-checkstyle-plugin',
                                        'MCHECKSTYLE'),
            'maven-war-plugin': ('https://github.com/apache/maven-war-plugin', 'MWAR'),
            'maven-jmod-plugin': ('https://github.com/apache/maven-jmod-plugin', 'MJMOD'),
            'commons-dbutils': ('https://github.com/apache/commons-dbutils', 'DBUTILS'),
            'lens': ('https://github.com/apache/lens', 'LENS'),
            'abdera': ('https://github.com/apache/abdera', 'ABDERA'),
            'maven-stage-plugin': ('https://github.com/apache/maven-stage-plugin',
                                   'MSTAGE'),
            'maven-source-plugin': ('https://github.com/apache/maven-source-plugin',
                                    'MSOURCES'),
            'atlas': ('https://github.com/apache/atlas', 'ATLAS'),
            'hive': ('https://github.com/apache/hive', 'HIVE'),
            'maven-plugin-tools': ('https://github.com/apache/maven-plugin-tools',
                                   'MPLUGIN'),
            'cxf-xjc-utils': ('https://github.com/apache/cxf-xjc-utils', 'CXFXJC'),
            'commons-numbers': ('https://github.com/apache/commons-numbers', 'NUMBERS'),
            'bookkeeper': ('https://github.com/apache/bookkeeper', 'BOOKKEEPER'),
            'karaf': ('https://github.com/apache/karaf', 'KARAF'),
            'maven-doxia-sitetools': ('https://github.com/apache/maven-doxia-sitetools',
                                      'DOXIASITETOOLS'),
            'drill': ('https://github.com/apache/drill', 'DRILL'),
            'maven-pmd-plugin': ('https://github.com/apache/maven-pmd-plugin', 'MPMD'),
            'sis': ('https://github.com/apache/sis', 'SIS'),
            'tiles-request': ('https://github.com/apache/tiles-request', 'TREQ'),
            'commons-chain': ('https://github.com/apache/commons-chain', 'CHAIN'),
            'systemml': ('https://github.com/apache/systemml', 'SYSTEMML'),
            'ignite': ('https://github.com/apache/ignite', 'IGNITE'),
            'commons-csv': ('https://github.com/apache/commons-csv', 'CSV'),
            'hbase': ('https://github.com/apache/hbase', 'HBASE'),
            'maven-antrun-plugin': ('https://github.com/apache/maven-antrun-plugin',
                                    'MANTRUN'),
            'usergrid': ('https://github.com/apache/usergrid', 'USERGRID'),
            'commons-jxpath': ('https://github.com/apache/commons-jxpath', 'JXPATH'),
            'cocoon': ('https://github.com/apache/cocoon', 'COCOON'),
            'wookie': ('https://github.com/apache/wookie', 'WOOKIE'),
            'maven-scm': ('https://github.com/apache/maven-scm', 'SCM'),
            'commons-jci': ('https://github.com/apache/commons-jci', 'JCI'),
            'commons-jcs': ('https://github.com/apache/commons-jcs', 'JCS'),
            'flume': ('https://github.com/apache/flume', 'FLUME'),
            'nuvem': ('https://github.com/apache/nuvem', 'NUVEM'),
            'dubbo': ('https://github.com/apache/dubbo', 'DUBBO'),
            'oozie': ('https://github.com/apache/oozie', 'OOZIE'),
            'jackrabbit-filevault': ('https://github.com/apache/jackrabbit-filevault',
                                     'JCRVLT'),
            'ctakes': ('https://github.com/apache/ctakes', 'CTAKES'),
            'clerezza': ('https://github.com/apache/clerezza', 'CLEREZZA'),
            'streams': ('https://github.com/apache/streams', 'STREAMS'),
            'commons-cli': ('https://github.com/apache/commons-cli', 'CLI'),
            'commons-math': ('https://github.com/apache/commons-math', 'MATH'),
            'myfaces': ('https://github.com/apache/myfaces', 'MYFACES'),
            'jspwiki': ('https://github.com/apache/jspwiki', 'JSPWIKI'),
            'servicemix-components': ('https://github.com/apache/servicemix-components',
                                      'SMXCOMP'),
            'camel': ('https://github.com/apache/camel', 'CAMEL'),
            'james-hupa': ('https://github.com/apache/james-hupa', 'HUPA'),
            'commons-vfs': ('https://github.com/apache/commons-vfs', 'VFS'),
            'hadoop-hdfs': ('https://github.com/apache/hadoop-hdfs', 'HDFS'),
            'maven-scm-publish-plugin': ('https://github.com/apache/maven-scm-publish-plugin',
                                         'MSCMPUB'),
            'geronimo-devtools': ('https://github.com/apache/geronimo-devtools',
                                  'GERONIMODEVTOOLS'),
            'knox': ('https://github.com/apache/knox', 'KNOX'),
            'maven': ('https://github.com/apache/maven', 'MNG'),
            'commons-scxml': ('https://github.com/apache/commons-scxml', 'SCXML'),
            'james-postage': ('https://github.com/apache/james-postage', 'POSTAGE'),
            'jackrabbit-ocm': ('https://github.com/apache/jackrabbit-ocm', 'OCM'),
            'commons-exec': ('https://github.com/apache/commons-exec', 'EXEC'),
            'commons-bcel': ('https://github.com/apache/commons-bcel', 'BCEL')}



def layout(repo_path, commit_id):
    java = set()
    tests = set()
    repo = git.Repo(repo_path)
    files = repo.git.ls_tree("-r", "--name-only", commit_id).split()
    for f in filter(lambda x: x.endswith('.java'), files):
            if 'test' in f:
                tests.add(os.path.dirname(f))
            else:
                java.add(os.path.dirname(f))
    reduced_java = set()
    s_j = min(list(map(lambda x: len(x), java)))
    min_java_name = list(filter(lambda x: len(x) == s_j, java))[0]
    reduced_tests = set()
    s_t = min(list(map(lambda x: len(x), tests)))
    min_test_name = list(filter(lambda x: len(x) == s_t, tests))[0]
    for name in java:
        if os.path.dirname(name) in java:
            continue
        if name != min_java_name and name[:s_j] == min_java_name:
            continue
        reduced_java.add(name)
    for name in tests:
        if os.path.dirname(name) in tests:
            continue
        if name != min_test_name and name[:s_t] == min_test_name:
            continue
        reduced_tests.add(name)
    commond_java = os.path.commonpath(reduced_java)
    if not commond_java:
        commond_java = sorted(reduced_java, key=lambda x: len(x))[0]
    commond_tests = os.path.commonpath(reduced_tests)
    if not commond_tests:
        commond_tests = sorted(reduced_tests, key=lambda x: len(x))[0]
    return os.path.normpath(commond_java), os.path.normpath(commond_tests)
    # with open(out_file, 'w') as f:
    #     f.writelines(map(lambda x: x + '\n', [commond_java, commond_tests]))


def diff_on_layouts(repo_path, commit_a, commit_b, src_patch, test_patch):
    java_a, test_a = layout(repo_path, commit_a)
    java_b, test_b = layout(repo_path, commit_b)
    assert java_a == java_b
    assert test_a == test_b
    diff_src = f"git diff --no-ext-diff --binary {commit_a} {commit_b} {java_a}".split()
    diff_test = f"git diff --no-ext-diff --binary {commit_a} {commit_b} {test_a}".split()
    print(diff_src)
    with open(src_patch, 'w') as out:
        run(diff_src, cwd=repo_path, stdout=out)
    with open(test_patch, 'w') as out:
        run(diff_test, cwd=repo_path, stdout=out)

    # TODO: check patches are not empty

def fix_mvn_compiler(file_name):
    with open(file_name) as f:
        lines = f.readlines()
    lines2 = []
    for l in lines:
        if l.startswith('maven.compile.source='):
            l = 'maven.compile.source=1.7\n'
        if l.startswith('maven.compile.target='):
            l = 'maven.compile.target=1.7\n'
        lines2.append(l)
    with open(file_name,'w') as f:
        f.writelines(lines2)


def fix_mvn_compiler_dir(dir_name):
    for root, _, files in os.walk(dir_name):
        for name in files:
            if name == 'maven-build.properties':
                fix_mvn_compiler(os.path.join(root, name))


class Reproducer:
    def __init__(self, p, working_dir, ind):
        # consts
        self.dir = os.path.abspath(os.path.dirname(__file__))
        self.script_dir = os.path.dirname(self.dir)
        self.projects_dir = os.path.join(self.script_dir, 'projects')
        self.const_core_dir = os.path.join(self.script_dir, 'core')
        self.lib_dir = os.path.join(self.script_dir, 'lib')
        self.util_dir = os.path.join(self.script_dir, 'util')
        self.base_dir = os.path.dirname(self.script_dir)
        self.conts_repo_dir = os.path.join(self.base_dir, 'project_repos')
        self.d4j_tmp_dir = '/tmp/versions'
        self.major_root = os.path.join(self.base_dir, 'major')
        self.d4j_build_file = os.path.join(self.projects_dir, 'defects4j.build.xml')

        # scripts cmds
        self.p = p
        self.pid = projects[p][1].title()
        self.working_dir = os.path.abspath(working_dir)
        self.project_dir = os.path.join(self.working_dir, 'framework', 'projects', self.pid)
        self.ind = ind
        getters = {'p': projects[p][1].title(), 'r': projects[p][0], 'n': p, 'g': 'jira', 't': projects[p][1],
                   'e': '"/({0}-\d+)/mi"'.format(projects[p][1]), 'w': working_dir, 'i': ind,
                   'a': f"{working_dir}//project_repos//{p}.git",
                   'b': f"{working_dir}//framework//projects//{projects[p][1].title()}//active-bugs.csv",
                   'o': f"{working_dir}//issues", 'f': f"{working_dir}//issues.txt", 'q': '',
                   'l': f"{working_dir}//gitlog"}
        self.name = p
        self.url = projects[self.p][0]
        self.jira_key = projects[p][1]
        self.work_dir = working_dir
        self.active_bugs = f"{working_dir}//framework//projects//{projects[p][1].title()}//active-bugs.csv"
        self.module_template = os.path.join(self.const_core_dir, "Project", "template")
        self.build_template = os.path.join(self.projects_dir, 'template.build.xml')
        self.build_file = os.path.join(self.project_dir, self.pid + '.build.xml')
        self.build_patch = os.path.join(self.projects_dir, 'build.xml.patch')
        self.build_patch_file = os.path.join(self.project_dir, 'build.xml.patch')
        self.repo_dir = os.path.join(self.working_dir, 'project_repos')
        self.issues_dir = os.path.join(self.working_dir, 'issues')
        self.patch_dir = os.path.join(self.project_dir, 'patches')
        self.failing_dir = os.path.join(self.project_dir, 'failing_tests')
        self.trigger_dir = os.path.join(self.project_dir, 'trigger_tests')
        self.relevant_dir = os.path.join(self.project_dir, 'relevant_tests')
        self.mod_classes = os.path.join(self.project_dir, 'modified_classes')
        self.rel_classes = os.path.join(self.project_dir, 'loaded_classes')
        self.core_dir = os.path.join(self.working_dir, 'framework', 'core', 'Project')
        self.module_file = os.path.join(self.core_dir, self.pid + '.pm')
        self.analyzer_output = os.path.join(self.project_dir, 'analyzer_output')
        self.gen_buildfile_dir = os.path.join(self.project_dir, 'build_files')

    def create_project(self):
        for d in [self.project_dir, self.core_dir, self.issues_dir, self.patch_dir, self.failing_dir, self.trigger_dir,
                  self.relevant_dir, self.mod_classes, self.rel_classes, self.analyzer_output, self.gen_buildfile_dir]:
            os.makedirs(d, exist_ok=True)
        for src, dst in [(self.module_template, self.module_file), (self.build_template, self.build_file),
                         (self.build_patch, self.build_patch_file)]:
            with open(src) as src_f:
                lines = list(
                    map(lambda l: l.replace('<PID>', self.pid).replace('<PROJECT_NAME>', self.name), src_f.readlines()))
            with open(dst, 'w') as dst_f:
                dst_f.writelines(lines)
        os.makedirs(self.repo_dir, exist_ok=True)
        os.system(f"git clone --bare {self.url} {self.repo_dir}/{self.name}.git")
        os.system(f"git clone {self.url} {self.repo_dir}/{self.name}_real.git")
        # run(f"git clone {self.url} {os.path.abspath(self.repo_dir)}/{self.name}.git".split())

    def extract_issues(self):
        repo_path = os.path.join(self.repo_dir, self.name + ".git")
        extract_issues(repo_path, self.jira_key, self.active_bugs)

    def init_version(self):
        repo = git.Repo.clone_from(f"{self.repo_dir}/{self.name}.git", f"{self.repo_dir}/{self.name}_init.git")
        fix, buggy = self.get_commits()
        repo.git.checkout(fix, force=True)
        if 'pom.xml' in os.listdir(repo.working_dir):
            sf = SourceFixer(repo.working_dir)
            sf.set_compiler_version('1.8')
            os.system(f"cd {self.repo_dir}/{self.name}_init.git && mvn ant:ant -Doverwrite=true 2>&1 -Dhttps.protocols=TLSv1.2 -Dmaven.compile.source=1.8 -Dmaven.compile.target=1.8")
            fix_mvn_compiler_dir(repo.working_dir)
            build_files_dir = os.path.join(self.gen_buildfile_dir, fix + '___')
            os.mkdir(build_files_dir)
            os.system(f"cd {self.repo_dir}/{self.name}_init.git && cp maven-build.* {build_files_dir}")
            os.system(f"cd {self.repo_dir}/{self.name}_init.git && cp build.xml {build_files_dir}")
            os.system(f"cd {self.repo_dir}/{self.name}_init.git && sed \'s\/https:\\/\\/oss\\.sonatype\\.org\\/content\\/repositories\\/snapshots\\//http:\\/\\/central\\.maven\\.org\\/maven2\\/\/g\' maven-build.xml >> temp && mv temp maven-build.xml")
            os.system(f"cd {self.repo_dir}/{self.name}_init.git && ant -Dmaven.repo.local=\"{os.path.join(self.project_dir, 'lib')}\" get-deps")

    def get_diffs(self):
        repo_path = os.path.abspath(os.path.join(self.repo_dir, self.name + "_real.git"))
        commit_a, commit_b = self.get_commits()
        print(repo_path)
        diff_on_layouts(repo_path, commit_a, commit_b,
                        os.path.join(self.patch_dir, self.ind + '.src.patch'),
                        os.path.join(self.patch_dir, self.ind + '.test.patch'))

    def get_commits(self):
        df = pd.read_csv(self.active_bugs)
        fix, buggy = df[df['bug.id'] == int(self.ind)][['revision.id.fixed', 'revision.id.buggy']].values[
            0].tolist()
        return fix, buggy

    def do_all(self):
        self.create_project()
        self.extract_issues()
        self.get_diffs()
        self.init_version()


def get_cmds(p, working_dir, ind):
    reproducer = Reproducer(p, working_dir, ind)
    reproducer.do_all()
    getters = {'p': projects[p][1].title(), 'r': projects[p][0], 'n': p, 'g': 'jira', 't': projects[p][1],
               'e': '"/({0}-\d+)/mi"'.format(projects[p][1]), 'w': working_dir, 'i': ind,
               'a': f"{working_dir}//project_repos//{p}.git",
               'b': f"{working_dir}//framework//projects//{projects[p][1].title()}//active-bugs.csv",
               'o': f"{working_dir}//issues", 'f': f"{working_dir}//issues.txt", 'q': '', 'l': f"{working_dir}//gitlog"}
    files_cmds = [(['./initialize-revisions.pl'], ['p', 'w', 'i']),
                  (['./analyze-project.pl'], ['p', 'w', 'g', 't', 'i']),
                  (['./get-trigger.pl'], ['p', 'w'])]
    for f in files_cmds:
        yield f[0] + reduce(list.__add__, list(map(lambda x: [f'-{x}', getters[x]], f[1])), [])


if __name__ == '__main__':
    project_name = sys.argv[1]
    working_dir = sys.argv[2]
    ind = sys.argv[3]
    with open('./run.sh', 'w') as f:
        for c in get_cmds(project_name, working_dir, ind):
            f.write(" ".join(c) + '\n')
