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

def fix(candidates):
    for c in candidates:
        if 'test' in c.lower():
            try:
                os.remove(c)
            except Exception as e:
                pass

    
if __name__ == '__main__':
    print('fix_compile_errors', sys.argv)
    fix(get_candidates(sys.argv[1], sys.argv[2]))