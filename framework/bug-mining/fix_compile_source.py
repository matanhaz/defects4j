import os
import sys

def fix(file_name):
    with open(file_name) as f:
        lines = f.readlines()
    lines2 = []
    for l in lines:
        if l.startswith('maven.compile.source='):
            l = 'maven.compile.source=1.8\n'
        if l.startswith('maven.compile.target='):
            l = 'maven.compile.target=1.8\n'
        lines2.append(l)
    with open(file_name,'w') as f:
        f.writelines(lines2)

def fix_dir(dir_name):
    for root, _, files in os.walk(dir_name):
        for name in files:
            if name == 'maven-build.properties':
                fix(os.path.join(root, name))

fix_dir(sys.argv[1])
