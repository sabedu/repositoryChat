import pandas as pd
import json
import logging
from scripts.core import RSZZ
import os


class LinkBugs():
    def __init__(self, repo_url):
        self.repo_url = repo_url
        self.repo_name = repo_url.split("/")[-1]
        self.repo_owner = repo_url.split("/")[-2]
        self.repo_dir = f"repos/{self.repo_name}"
        self.issue_json = f"data/{self.repo_name}/{self.repo_name}_issues.json"
        self.updated_issue_json = f"data/{self.repo_name}/new_{self.repo_name}_issues.json"
        self.output = f"data/{self.repo_name}/{self.repo_name}_fixing_bic.json"
        self.updated_output = f"data/new_{self.repo_name}/{self.repo_name}_fixing_bic.json"

        # if not os.path.exists(self.repo_dir):
        #     os.makedirs(self.repo_dir)
        #     try:
        #         os.system(f"git clone {self.repo_url} {self.repo_dir}")
        #         logging.info(f"Repository {self.repo_name} cloned successfully")
        #     except Exception as e:
        #         logging.error(f"Error cloning repository: {e}")
        # else:
        #     logging.info(f"Repository {self.repo_name} already exists")
        #     os.system(f"git -C {self.repo_dir} pull")

        logging.basicConfig(filename=f'{self.repo_owner}_{self.repo_name}_console.log', filemode='w',
                            format='%(name)s - %(levelname)s - %(message)s', level=logging.INFO)

    def process_issues(self, updated=False):
        try:
            if updated:
                issues_df = pd.read_json(self.updated_issue_json)
            else:
                issues_df = pd.read_json(self.issue_json)
        except FileNotFoundError:
            print("No issues file found.")
            return
        # if not os.path.exists(self.output):
        #     issues_df = pd.read_json(self.issue_json)
        # else:
        #     try:
        #         issues_df = pd.read_json(self.updated_issue_json)
        #     except FileNotFoundError:
        #         print("No updated issues file found.")
        #         return
        results = self.process_issues_df(issues_df)

        if not os.path.exists(self.output):
            self.write_results_to_file(results, self.output)
        else:
            self.update_existing_results(results, self.output)
        print("SZZ execution completed successfully")
        return results

    def process_issues_df(self, issues_df):
        results = []
        for row in issues_df.itertuples():
            bug_id = str(row.number)
            logging.info(f"Processing bug {bug_id}")
            result = self.create_result_structure(row, bug_id)
            self.process_fixing_commits(result, bug_id)
            results.append(result)
        return results

    def create_result_structure(self, row, bug_id):
        return {
            "URL": row.url,
            "Title": row.title,
            "Number": bug_id,
            "FixingCommit": [],
            "InducingCommit": [],
            "ImpactedFiles": []
        }

    def process_fixing_commits(self, result, bug_id):
        self.r_szz_instance = RSZZ(repo_full_name=self.repo_name, repo_url=self.repo_url, repos_dir="repos")
        fixing_commits = self.r_szz_instance.find_bug_fix_commit(bug_id)
        if fixing_commits:
            for fixing_commit in fixing_commits:
                logging.info(f"Processing fixing commit {fixing_commit}")
                result["FixingCommit"].append(fixing_commit)
                impacted_files = self.r_szz_instance.get_impacted_files(fixing_commit)
                bic = self.r_szz_instance.find_bic(fixing_commit, impacted_files)
                self.add_impacted_files_and_bics(result, impacted_files, bic)

    def add_impacted_files_and_bics(self, result, impacted_files, bic):
        for impacted_file in impacted_files:
            filename = impacted_file.file_path.split("/")[-1]
            result["ImpactedFiles"].append(filename)
        for commit in bic:
            if commit is not None:
                result["InducingCommit"].append(commit.hexsha)

    def write_results_to_file(self, results, file_path):
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=4)

    def update_existing_results(self, results, file_path):
        with open(file_path, 'r+', encoding='utf-8') as f:
            existing_data = json.load(f)
            existing_data.extend(results)
            f.seek(0)
            f.truncate()
            json.dump(existing_data, f, ensure_ascii=False, indent=4)