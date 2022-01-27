import os
import sys
import time
from datetime import datetime
from functools import reduce
from urllib.parse import urlparse

import pandas as pd
from git import Repo
from jira import JIRA


class Issue(object):
    def __init__(self, issue_id, type, priority, resolution, url, creation_time):
        self.issue_id = issue_id
        self.type = type
        self.priority = priority
        self.resolution = resolution
        self.url = url
        self.creation_time = creation_time

    def to_saveable_dict(self):
        return {'issue_id': self.issue_id, 'type': self.type, 'priority': self.priority, 'resolution': self.resolution,
                'url': self.url, 'creation_time': self.creation_time}

    def to_features_dict(self):
        return {'issue_id': self.issue_id, 'type': self.type, 'priority': self.priority, 'resolution': self.resolution}


class JiraIssue(Issue):
    def __init__(self, issue, base_url):
        super().__init__(issue.key.strip().split('-')[1], issue.fields.issuetype.name.lower(),
                         JiraIssue.get_name_or_default(issue.fields.priority, 'minor'),
                         JiraIssue.get_name_or_default(issue.fields.resolution, 'resolved'), base_url,
                         datetime.strptime(issue.fields.created, "%Y-%m-%dT%H:%M:%S.%f%z"))
        self.fields = {}
        for k, v in dict(issue.fields.__dict__).items():
            if k.startswith("customfield_") or k.startswith("__"):
                continue
            if type(v) in [str, type(None), type(0), type(0.1)]:
                self.fields[k] = str(v)
            elif hasattr(v, 'name'):
                self.fields[k] = v.name.replace('\n', '').replace(';', '.,')
            elif type(v) in [list, tuple]:
                lst = []
                for item in v:
                    if type(item) in [str]:
                        lst.append(item)
                    elif hasattr(item, 'name'):
                        lst.append(item.name)
                self.fields[k] = "@@@".join(lst)
        for k in self.fields:
            self.fields[k] = ' '.join(self.fields[k].split())

    @staticmethod
    def get_name_or_default(val, default):
        if val:
            return val.name.lower()
        return default


def get_jira_issues(project_name, url="http://issues.apache.org/jira", bunch=100):
    jira_conn = jira.JIRA(url)
    all_issues = []
    extracted_issues = 0
    sleep_time = 30
    while True:
        try:
            issues = jira_conn.search_issues("project={0}".format(project_name), maxResults=bunch,
                                             startAt=extracted_issues)
            all_issues.extend(issues)
            extracted_issues = extracted_issues + bunch
            if len(issues) < bunch:
                break
        except Exception as e:
            sleep_time = sleep_time * 2
            if sleep_time >= 480:
                raise e
            time.sleep(sleep_time)
    return list(map(lambda issue: JiraIssue(issue, url), all_issues))


class Commit(object):
    def __init__(self, bug_id, git_commit, issue=None, files=None, is_java_commit=True):
        self._commit_id = git_commit.hexsha
        self._repo_dir = git_commit.repo.working_dir
        self._issue_id = bug_id
        if files:
            self._files = files
        else:
            self._files = list(map(lambda f: CommittedFile(self._commit_id, f, '0', '0'), git_commit.stats.files.keys()))
        self._methods = list()
        self._commit_date = time.mktime(git_commit.committed_datetime.timetuple())
        self._commit_formatted_date = datetime.utcfromtimestamp(self._commit_date).strftime('%Y-%m-%d %H:%M:%S')
        self.issue = issue
        if issue:
            self.issue_type = self.issue.type
        else:
            self.issue_type = ''
        self.is_java_commit = is_java_commit
        self.is_all_tests = all(list(map(lambda x: not x.is_test, self._files)))

    @classmethod
    def init_commit_by_git_commit(cls, git_commit, bug_id='0', issue=None, files=None, is_java_commit=True):
        return Commit(bug_id, git_commit, issue, files=files, is_java_commit=is_java_commit)


def _commits_and_issues(repo, jira_issues):
    issues = dict(map(lambda x: (x.issue_id, x), jira_issues))
    issues_dates = sorted(list(map(lambda x: (x, issues[x].creation_time), issues)), key=lambda x: x[1], reverse=True)
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

    commits = []
    java_commits = _get_commits_files(repo)
    for commit_sha in java_commits:
        git_commit = repo.commit(commit_sha)
        bug_id = "0"
        if all(list(map(lambda x: not x.is_java, java_commits[commit_sha]))):
            commit = Commit.init_commit_by_git_commit(git_commit, bug_id, None, java_commits[commit_sha], False)
            commits.append(commit)
            continue
        try:
            commit_text = _clean_commit_message(git_commit.message)
        except Exception as e:
            continue
        ind = 0
        for ind, (issue_id, date) in enumerate(issues_dates):
            date_ = date
            if date_.tzinfo:
                date_ = date_.replace(tzinfo=None)
            if git_commit.committed_datetime.replace(tzinfo=None) > date_:
                break
        issues_dates = issues_dates[ind:]
        bug_id = get_bug_num_from_comit_text(commit_text, set(map(lambda x: x[0], issues_dates)))
        commits.append(
            Commit.init_commit_by_git_commit(git_commit, bug_id, issues.get(bug_id), java_commits[commit_sha]))
    return commits


class JiraExtractor():

    def __init__(self, repo_dir, issues_path, active_bugs):
        self.repo = Repo(repo_dir)
        self.active_bugs = active_bugs
        self.issues_path = issues_path
        self.inspected_branch = self.repo.branches[0].name
        self.java_commits = self.get_java_commits()
        # issues = get_jira_issues(jira_key)
        self.issues_d = self.commits_and_issues()

    def fix(self):
        detailed_issues = dict(reduce(list.__add__, list(
            map(lambda commits: list(map(lambda c: ((self.get_parent(c).hexsha, c.hexsha), commits[0]), commits[1])),
                self.issues_d.items())), []))
        # detailed_issues.update(dict(self.check_active_bugs()))
        active = list(map(
            lambda x: (x[0] + 1, x[1][0][0], x[1][0][1], 'TEMP-' + x[1][1], 'https://issues.apache.org/jira/browse'),
            enumerate(detailed_issues.items())))
        df = pd.DataFrame(active,
                          columns=['bug.id', 'revision.id.buggy', 'revision.id.fixed', 'report.id', 'report.url'])
        df.to_csv(self.active_bugs, index=False)

    def get_java_commits(self):
        data = self.repo.git.log('--pretty=format:"sha: %H"', '--name-only').split("sha: ")
        comms = dict(map(lambda d: (d[0], list(
            filter(lambda x: x.endswith(".java") and 'test' not in os.path.normpath(x).split(os.path.sep)[-1].lower(),
                   d[1:-1]))), list(map(lambda d: d.replace('"', '').replace('\n\n', '\n').split('\n'), data))))
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
        df = pd.read_csv(self.active_bugs, header=None)
        df.columns = ['bug.id', 'revision.id.buggy', 'revision.id.fixed', 'report.id', 'report.url']
        df = df[['revision.id.buggy', 'revision.id.fixed', 'report.id']]
        if df.loc[0]['revision.id.buggy'] == 'revision.id.buggy':
            df = df.drop(0)
        for (ind, (b, f, i)) in df.iterrows():
            if self.repo.commit(f).parents[0].hexsha == b:
                files = self.java_commits.get(self.repo.commit(f), [])
            else:
                files = self.repo.git.diff(b, f, '--name-only').split('\n')
            java_files = list(filter(lambda x: x.endswith('.java'), files))
            src_files = list(filter(lambda x: 'test' not in x, java_files))
            if src_files:
                yield ((b, f), i.split('-')[1])

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
        issues_ids = list(
            map(lambda issue: issue.split("-")[1], pd.read_csv(self.issues_path, header=None)[0].to_list()))
        for git_commit in self.java_commits:
            if not self.has_parent(git_commit):
                continue
            commit_text = clean_commit_message(git_commit.summary)
            bug_id = get_bug_num_from_comit_text(commit_text, issues_ids)
            if bug_id != '0':
                issues_d.setdefault(bug_id, []).append(git_commit)
            elif any(map(lambda x: 'test' in x, self.java_commits[git_commit])) and any(
                    map(lambda x: 'test' not in x, self.java_commits[git_commit])):
                pass  # issues_d.setdefault("123456789", []).append(git_commit)
        return issues_d


if __name__ == '__main__':
    repo_dir = sys.argv[2]
    working_dir = sys.argv[4]
    active_bugs = sys.argv[6]
    JiraExtractor(repo_dir=repo_dir, issues_path=os.path.join(working_dir, 'issues.txt'), active_bugs=active_bugs).fix()
