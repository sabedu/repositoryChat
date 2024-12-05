import logging as log
from operator import attrgetter
from typing import List, Set

import re
from collections import defaultdict

from git import Repo, Commit

from scripts.core.szz_core.abstract_szz import ImpactedFile
from scripts.core.szz_core.variations.ma_szz import MASZZ
from scripts.core.szz_core.commands import CommandRunner


class RSZZ(MASZZ):
    """
    Recent-SZZ implementation.

    Da Costa, D. A., McIntosh, S., Shang, W., Kulesza, U., Coelho, R., & Hassan, A. E. (2016). A framework for
    evaluating the results of the szz approach for identifying bug-introducing changes. IEEE Transactions on Software
    Engineering.

    Supported **kwargs:
    todo:
    """

    def __init__(self, repo_full_name: str, repo_url: str, repos_dir: str = None):
        super().__init__(repo_full_name, repo_url, repos_dir)
        self.repos_dir = f'{repos_dir}/{repo_full_name}'

    # TODO: implement logic for finding bug fixing commit through regular expression
    def find_bug_fixing_commit(self, bug_id: str) -> List[str]:
        """
        Find commits that fix a bug by searching for the bug ID in commit messages.

        :param bug_id: The ID of the bug as recorded in the change log.
        :return: A list of commit hashes that are identified as bug-fixing for the given bug ID.
        """
        fixing_commits = []
        repo = Repo(self.repos_dir)
        for commit in repo.iter_commits():
            if re.search(bug_id, commit.message, re.IGNORECASE):
                # Optionally verify with ITS here if applicable
                fixing_commits.append(commit.hexsha)
        return fixing_commits
    
    # TODO: implement logic for finding bug fixing commit through git log command
    def find_bug_fix_commit(self, bug_id: str) -> List[str]:
        fixing_commit = []
        bug_pattern = f'#{bug_id}([ \\n.,;)|]|$)|issues/{bug_id}([ \\n.,;)|]|$)'
        gitcommand = CommandRunner(self.repos_dir)
        stdout, stderr = gitcommand.run_command(['log', '--all', '--extended-regexp', '--grep', bug_pattern, '--format=%H'])
        if stderr:
            print(stderr)
            return []
        stdout = stdout.strip()
        if stdout:
            commit_lines = stdout.split('\n')
            if commit_lines:
                commit_hash, *commit_message = commit_lines[0].split(' ', 1)
                fixing_commit.append(commit_hash)
                # return {"CommitHash": commit_hash, "Message": commit_message[0] if commit_message else ""}, None
                return fixing_commit
        print("Commit not found")
        return []
    
    # TODO: implement logic for indexing bug id in commit message (to achieve O(m) complexity)
    def index_bug_id(self) -> None:
        bug_id_index = defaultdict(list)
        
        # Regular expression to match bug IDs in commit messages
        # bug_id_escape = re.escape(str(bug_id))
        # bug_id_pattern = re.compile(rf'#{bug_id_escape}([ \n.,;)|\]]|$)|issues/{bug_id_escape}([ \n.,;)|\]]|$)')
        bug_id_pattern = re.compile(r'#(\d+)([ \n.,;)|\]]|$)|issues/(\d+)([ \n.,;)|\]]|$)')
        # bug_id_pattern = re.compile(r'#(\d+)')
        
        # Extract commit hash and messages
        gitcommand = CommandRunner(self.repos_dir)
        stdout, stderr = gitcommand.run_command(['log', '--all', '--format=%H %B'])

        if stderr:
            print(stderr)
            return bug_id_index
        
        for line in stdout.split('\n'):
            print(line)
            # Try to find a bug ID in the commit message
            match = bug_id_pattern.search(line)
            if match:
                for i in range(1, len(match.groups()) + 1):
                    if match.group(i):
                        bug_id = match.group(i)
                commit_hash = line.split(' ')[0]  # Assuming the first word is the commit hash
                bug_id_index[bug_id].append(commit_hash)
        
        return bug_id_index

    # TODO: add parse and type check on kwargs
    def find_bic(self, fix_commit_hash: str, impacted_files: List['ImpactedFile'], **kwargs) -> Set[Commit]:
        bic_candidates = super().find_bic(fix_commit_hash, impacted_files, **kwargs)

        return {RSZZ.select_latest_commit(bic_candidates)}

    @staticmethod
    def select_latest_commit(bic_candidates: Set[Commit]) -> Commit:
        latest_bic = None
        if len(bic_candidates) > 0:
            latest_bic = max(bic_candidates, key=attrgetter('committed_date'))
            log.info(f"selected bug introducing commit: {latest_bic.hexsha}")

        return latest_bic
