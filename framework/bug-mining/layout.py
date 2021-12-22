import os
import sys
import csv

def layout(repo_path, out_file):
	java = set()
	tests = set()
	for root, dirs, files in os.walk(repo_path, topdown=False):
		for name in filter(lambda x: x.endswith('.java'), files):
			if 'test' in root:
				tests.add(root[len(repo_path) + 1:])
			else:
				java.add(root[len(repo_path) + 1:])
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
	with open(out_file, 'w') as f:
		f.writelines(map(lambda x: x + '\n',[commond_java, commond_tests]))


if __name__ == '__main__':
	repo_dir = sys.argv[1]
	out_file = sys.argv[2]
	layout(repo_dir, out_file)
