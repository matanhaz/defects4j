
import pandas as pd
import os
import sys
from urllib.parse import urlparse
from functools import reduce
from jira import JIRA
from git import Repo
import settings


class JiraExtractor():

	def __init__(self, repo_dir, issues_path, active_bugs):
		self.repo = Repo(repo_dir)
		self.active_bugs = active_bugs
		self.issues_path = issues_path
		self.inspected_branch = repo.branches[0].name
		self.java_commits = self.get_java_commits()
		self.issues_d = self.commits_and_issues()
    
    def fix(self):
		detailed_issues = dict(reduce(list.__add__, list(map(lambda commits: list(map(lambda c: ((self.get_parent(c).hexsha, c.hexsha), commits[0]), commits[1])), self.issues_d.items())), []))
        detailed_issues.update(dict(self.check_active_bugs()))
        active = list(map(lambda x: (x[0] + 1, x[1][0][0],x[1][0][1], x[1][1], ''), enumerate(detailed_issues.items())))
        df = pd.DataFrame(active, columns=['bug.id','revision.id.buggy','revision.id.fixed','report.id','report.url'])
        df.to_csv(self.active_bugs, index=False)

	def get_java_commits(self):
		data = self.repo.git.log('--pretty=format:"sha: %H"', '--name-only').split("sha: ")
		comms = dict(map(lambda d: (d[0], list(filter(lambda x: x.endswith(".java"), d[1:-1]))), list(map(lambda d: d.replace('"', '').replace('\n\n', '\n').split('\n'), data))))
		return dict(map(lambda x: (self.repo.commit(x), comms[x]), list(filter(lambda x: comms[x], comms))))

	def has_parent(self, commit):
		return self.get_parent(commit) is not None

	def get_parent(self, commit):
		ans = None
		for curr_parent in commit.parents:
			for branch in curr_parent.repo.refs:
				if branch.name == self.inspected_branch:
					ans = curr_parent
					break
		return ans

    def check_active_bugs(self):
        df = pd.read_csv(self.active_bugs)[['revision.id.buggy', 'revision.id.fixed','report.id']]
        for (ind, (b,f,i)) in df.iterrows():
            files = self.repo.git.diff(b,f, '--name-only').split('\n')
            java_files = list(filter(lambda x: x.endswith('.java'), files))
            src_files = list(filter(lambda x: 'test' not in x, java_files))
            if src_files:
                yield ((b,f),i.split('-')[1])
    
	def commits_and_issues(self):
		def replace(chars_to_replace, replacement, s):
			temp_s = s
			for c in chars_to_replace:
				temp_s = temp_s.replace(c, replacement)
			return temp_s

		def get_bug_num_from_comit_text(commit_text, issues_ids):
			text = replace("[]?#,:(){}'\"", "", commit_text.lower())
			text = replace("-_.=", " ", text)
			text = text.replace('bug', '').replace('fix', '')
			for word in text.split():
				if word.isdigit():
					if word in issues_ids:
						return word
			return "0"

		def clean_commit_message(commit_message):
			if "git-svn-id" in commit_message:
				return commit_message.split("git-svn-id")[0]
			return commit_message

		issues_d = {}
		issues_ids = list(map(lambda issue: issue.split("-")[1], pd.read_csv(self.issues_path, header=None)[0].to_list()))
		for git_commit in self.java_commits:
			if not self.has_parent(git_commit):
				continue
			commit_text = clean_commit_message(git_commit.summary)
			bug_id = get_bug_num_from_comit_text(commit_text, issues_ids)
			if bug_id != '0':
				issues_d.setdefault(bug_id, []).append(git_commit)
			elif any(map(lambda x: 'test' in x, self.java_commits[git_commit])) and any(map(lambda x: 'test' not in x, self.java_commits[git_commit])):
				# check if it change a test file and java
				if self.issue_key is None:
					issues_d.setdefault("-1", []).append(git_commit)
		return issues_d


if __name__ == '__main__':
    repo_dir = sys.argv[2]
    working_dir = sys.argv[4]
    active_bugs = sys.argv[6]
	JiraExtractor(repo_dir=repo_dir, issues_path=os.path.join(working_dir, 'issues.txt'), active_bugs=active_bugs).fix()

