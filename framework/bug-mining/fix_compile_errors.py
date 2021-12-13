import os
import sys

def get_candidates(file_name, proj_dir):
    candidates = []
    with open(file_name) as f:
        for l in f.readlines():
            if 'error' in l and '.java' in l:
                if proj_dir in l:
                    c = proj_dir + l.split(proj_dir)[1].split('.java')[0] + '.java'
                    candidates.append(c)
    return candidates

def collect_failed_tests(failed_tests_file, proj_dir):
    candidates = []
    if not os.path.exists(failed_tests_file):
        return []
    with open(failed_tests_file) as f:
        failed_tests = list(map(lambda x: x.split('::')[0].split('.')[-1], map(lambda x: x[4:-1], filter(lambda l: l.startswith('---'), f.readlines()))))
    for root, _, files in os.walk(proj_dir):
        for f in files:
            for t in failed_tests:
                if t.lower() in f.lower():
                    candidates.append(os.path.join(root, f))
    return candidates

def fix(candidates):
    for c in set(candidates):
        if 'test' in c.lower():
            try:
                print(c)
                os.remove(c)
            except Exception as e:
                print(e)

    
if __name__ == '__main__':
    print('fix_compile_errors', sys.argv)
    fix(get_candidates(sys.argv[1], sys.argv[2].split('pl')[0]) + collect_failed_tests(os.path.join(os.path.dirname(sys.argv[1]), 'failing_tests.log'), sys.argv[2].split('pl')[0]))