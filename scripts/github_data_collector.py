import requests
from github import Github
import json
import os
from dotenv import load_dotenv
from logging import getLogger
import subprocess
from datetime import datetime
import time

logger = getLogger(__name__)
load_dotenv()


class GitHubDataCollector:
    def __init__(self, token, repo_url):
        self.github = Github(token)
        self.repo_url = repo_url
        self.repo_owner = repo_url.split("/")[-2]
        self.repo_name = repo_url.split("/")[-1]
        self.base_dir = f'data/{self.repo_name}'
        self.repo_path = f'repos/{self.repo_name}'
        os.makedirs(self.base_dir, exist_ok=True)
        self.headers = {"Authorization": f"Bearer {token}"}
        # self.repo = self.github.get_repo(f"{self.repo_owner}/{self.repo_name}")
        if not os.path.exists(self.repo_path):
            os.makedirs(self.repo_path)
            try:
                os.system(f"git clone {self.repo_url} {self.repo_path}")
                logger.info(f"Repository {self.repo_name} cloned successfully")
            except Exception as e:
                logger.error(f"Error cloning repository: {e}")
        else:
            logger.info(f"Repository {self.repo_name} already exists")
            os.system(f"git -C {self.repo_path} pull")
        logger.info(f"Created instance of GithubDataCollector")

    def query_graphql(self, query, variables):
        logger.info(f"Executing GraphQL query with variables: {variables}")
        try:
            payload = {"query": query, "variables": variables}
            response = requests.post('https://api.github.com/graphql', json=payload, headers=self.headers, timeout=60)

            if response.status_code != 200:
                error_message = f"GraphQL query failed with status code {response.status_code}: {response.text}"
                logger.exception(error_message)
                raise Exception(error_message)
            remaining_requests = int(response.headers.get('X-RateLimit-Remaining', 1))
            if remaining_requests == 0:
                reset_time = int(response.headers.get('X-RateLimit-Reset', time.time()))
                sleep_duration = max(reset_time - time.time(), 0)
                logger.warning(f"Rate limit exceeded. Sleeping for {sleep_duration} seconds.")
                time.sleep(sleep_duration)
            return response.json()['data']
        except requests.exceptions.Timeout as e:
            logger.error(f"Request timed out: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Error occurred while querying graphql: {e}", exc_info=True)
            return {}

    def get_all_instances_of_entity(self, entity, after_cursor=None):
        logger.info(f"Getting all instances of {entity}, after_cursor: {after_cursor}")
        with open(f'queries/{entity}.graphql', 'r', encoding='utf-8') as file:
            query = file.read()

        variables = {
            'owner': self.repo_owner,
            'name': self.repo_name,
            'after_clause': after_cursor
        }

        return self.query_graphql(query=query, variables=variables)

    def run_git_command(self, args):
        try:
            result = subprocess.run(
                ['git'] + args,
                cwd=self.repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.error(f"Git command error: {e.stderr}")
            return None
        
    def get_repository_data(self):
        with open('queries/repository.graphql', 'r', encoding='utf-8') as file:
            query = file.read()

        file_path = f'{self.base_dir}/{self.repo_name}_repositories.json'

        variables = {'owner': self.repo_owner, 'name': self.repo_name}

        try:
            data = self.query_graphql(query=query, variables=variables)
            repository = data['repository']
        except Exception as e:
            logger.error(f"Error occurred while collecting repository data: {e}", exc_info=True)
            return

        repository_data = {
            "description": repository['description'],
            "id": repository['id'],
            "owner_login": repository['owner']['login'] if repository['owner'] != {} else None,
            "owner_name": repository['owner']['name'] if repository['owner'] != {} else None,
            'owner_id': repository['owner']['id'] if repository['owner'] != {} else None,
            'owner_email': repository['owner']['email'] if repository['owner'] != {} else None,
            "name": repository['name'],
            "url": repository['url'],
            "stars": repository['stargazerCount'],
            "visibility": repository['visibility'],
            'primaryLanguage': repository['primaryLanguage']['id'],
            'forksCount': repository['forkCount'],
            "isTemplate": repository['isTemplate'],
            "branches": repository.get('refs', []),
        }

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('[')
            json.dump(repository_data, f, ensure_ascii=False, indent=4)
            f.write(']')

    # def get_additional_commit_details(self, commit_sha):
    #     try:
    #         commit = self.repo.get_commit(sha=commit_sha)
    #         modified_files = [
    #             {
    #                 "filename": file.filename,
    #                 "change_type": file.status,
    #                 "additions": file.additions,
    #                 "deletions": file.deletions
    #             } for file in commit.files
    #         ]
    #         return modified_files
    #     except Exception as e:
    #         logger.error(f"Error occurred while getting additional commit details: {e}", exc_info=True)
    #         return []
        
    def get_additional_commit_details(self, commit_sha):
        logger.info(f"Collecting details for commit {commit_sha}")
        try:
            # Get the diff with stats for the commit
            diff_output = self.run_git_command([
                'show', '--pretty=', '--numstat', commit_sha
            ])

            modified_files = []
            if diff_output:
                for line in diff_output.strip().split('\n'):
                    if line:
                        parts = line.split('\t')
                        if len(parts) == 3:
                            additions, deletions, filename = parts
                            additions = int(additions) if additions.isdigit() else 0
                            deletions = int(deletions) if deletions.isdigit() else 0

                            # Get the diff content for the file
                            diff_content = self.run_git_command([
                                'show', f'{commit_sha}', '--', filename
                            ])

                            # Extract the change type
                            status_output = self.run_git_command([
                                'diff', '--name-status', f'{commit_sha}~1', commit_sha, '--', filename
                            ])
                            status_line = status_output.strip()

                            if status_line:
                                status_code, _ = status_line.split('\t', 1)
                                status = {
                                    'M': 'modified',
                                    'A': 'added',
                                    'D': 'deleted',
                                    'R': 'renamed',
                                    'C': 'copied',
                                    'T': 'type_changed',
                                    'U': 'unmerged'
                                }.get(status_code, 'unknown')
                            else:
                                status = 'unknown'

                            modified_files.append({
                                "filename": filename.split('/')[-1],
                                "path": filename,
                                "change_type": status,
                                "additions": additions,
                                "deletions": deletions,
                                "diff": diff_content
                            })
            return modified_files
        except Exception as e:
            logger.error(f"Error occurred while getting additional commit details: {e}", exc_info=True)
            return []


    # def collect_all_commits(self):
    #     logger.info("Collecting all commits")
    #     file_path = f'{self.base_dir}/{self.repo_name}_commits.json'

    #     with open(file_path, 'w', encoding='utf-8') as f:
    #         f.write('[')

    #     try:
    #         has_next_page = True
    #         after_cursor = None

    #         first_write = True

    #         while has_next_page:
    #             data = self.get_all_instances_of_entity('commits', after_cursor=after_cursor)
    #             repository_id = data['repository']['id']
    #             branch_id = data['repository']['defaultBranchRef']['id']
    #             commits = data['repository']['defaultBranchRef']['target']['history']['nodes']

    #             for commit in commits:
    #                 if commit['author']['user'] is None:
    #                     if commit['committer']['user'] is None:
    #                         logger.error(f"Commit with no author and no committer: {commit}")
    #                         continue
    #                 modified_files = self.get_additional_commit_details(commit['oid'])
    #                 comments_count = commit.get('comments', {}).get('totalCount', 0)
    #                 parents = commit.get('parents', [])
    #                 commit_data = {
    #                     'repository_id': repository_id,
    #                     'branch_id': branch_id,
    #                     "hash": commit['oid'],
    #                     "message": commit['message'],
    #                     "changed_files_if_available": commit['changedFilesIfAvailable'],
    #                     "additions": commit['additions'],
    #                     "deletions": commit['deletions'],
    #                     "comments_count": comments_count,
    #                     "abbreviatedOid": commit['abbreviatedOid'],
    #                     "committedDate": commit['committedDate'],
    #                     "parents": parents['nodes'],
    #                     "author_login": commit['author']['user']['login'] if commit['author']['user'] is not None else
    #                     commit['committer']['user']['login'] if commit['committer']['user'] is not None else None,
    #                     'author_id': commit['author']['user']['id'] if commit['author']['user'] is not None else
    #                     commit['committer']['user']['id'] if commit['committer']['user'] is not None else None,
    #                     'author_name': commit['author']['user']['name'] if commit['author']['user'] is not None else
    #                     commit['committer']['user']['name'] if commit['committer']['user'] is not None else None,
    #                     'author_email': commit['author']['user']['email'] if commit['author']['user'] is not None else
    #                     commit['committer']['user']['email'] if commit['committer']['user'] is not None else None,
    #                     "modified_files": modified_files
    #                 }

    #                 with open(file_path, 'a', encoding='utf-8') as f:
    #                     if not first_write:
    #                         f.write(',')
    #                     else:
    #                         first_write = False
    #                     json.dump(commit_data, f, ensure_ascii=False, indent=4)

    #             pageInfo = data['repository']['defaultBranchRef']['target']['history']['pageInfo']
    #             has_next_page = pageInfo['hasNextPage']
    #             after_cursor = pageInfo['endCursor']

    #         # with open(file_path, 'a', encoding='utf-8') as f:
    #         #     f.write(']')
    #     except Exception as e:
    #         logger.error(f"Error occurred while collecting commits: {e}", exc_info=True)
    #     finally:
    #         with open(file_path, 'a', encoding='utf-8') as f:
    #             f.write(']')

    def collect_all_commits(self):
        logger.info("Collecting all commits")
        file_path = os.path.join(self.base_dir, f'{self.repo_name}_commits.json')

        try:
            git_log_output = self.run_git_command([
                'log', '--pretty=format:%H%x09%an%x09%ae%x09%ad%x09%s', '--date=iso'
            ])

            if not git_log_output:
                logger.error("No commits found.")
                return

            commits = []
            for line in git_log_output.split('\n'):
                parts = line.strip().split('\t')
                if len(parts) >= 5:
                    commit_hash, author_name, author_email, committed_date, message = parts[:5]

                    modified_files = self.get_additional_commit_details(commit_hash)

                    branches_output = self.run_git_command([
                        'branch', '--contains', commit_hash
                    ])
                    branches = [branch.strip().replace('* ', '') for branch in branches_output.splitlines()]

                    commit_data = {
                        "hash": commit_hash,
                        "author_name": author_name,
                        "author_email": author_email,
                        "committedDate": datetime.strptime(committed_date, '%Y-%m-%d %H:%M:%S %z').isoformat(),
                        "message": message,
                        "branches": branches,
                        "modified_files": modified_files,
                    }
                    commits.append(commit_data)

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(commits, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"Error occurred while collecting commits: {e}", exc_info=True)


    # def update_commits(self, last_collected_date):
    #     file_path = f'{self.base_dir}/{self.repo_name}_commits.json'
    #     update_path = f'{self.base_dir}/new_{self.repo_name}_commits.json'
    #     has_next_page = True
    #     after_cursor = None

    #     try:
    #         if not os.path.exists(file_path):
    #             with open(file_path, 'w', encoding='utf-8') as f:
    #                 f.write('[]')

    #         while has_next_page:
    #             data = self.get_all_instances_of_entity('commits', after_cursor=after_cursor)
    #             repository_id = data['repository']['id']
    #             branch_id = data['repository']['defaultBranchRef']['id']
    #             commits = data['repository']['defaultBranchRef']['target']['history']['nodes']
    #             new_commits = []

    #             for commit in commits:
    #                 if commit['committedDate'] <= last_collected_date:
    #                     has_next_page = False
    #                     break

    #                 modified_files = self.get_additional_commit_details(commit['oid'])
    #                 comments_count = commit.get('comments', {}).get('totalCount', 0)
    #                 parents = commit.get('parents', [])
    #                 commit_data = {
    #                     'repository_id': repository_id,
    #                     'branch_id': branch_id,
    #                     "hash": commit['oid'],
    #                     "message": commit['message'],
    #                     "changed_files_if_available": commit['changedFilesIfAvailable'],
    #                     "additions": commit['additions'],
    #                     "deletions": commit['deletions'],
    #                     "comments_count": comments_count,
    #                     "abbreviatedOid": commit['abbreviatedOid'],
    #                     "committedDate": commit['committedDate'],
    #                     "parents": parents['nodes'],
    #                     "author_login": commit['author']['user']['login'] if commit['author']['user'] is not None else
    #                     commit['committer']['user']['login'] if commit['committer']['user'] is not None else None,
    #                     'author_id': commit['author']['user']['id'] if commit['author']['user'] is not None else
    #                     commit['committer']['user']['id'] if commit['committer']['user'] is not None else None,
    #                     'author_name': commit['author']['user']['name'] if commit['author']['user'] is not None else
    #                     commit['committer']['user']['name'] if commit['committer']['user'] is not None else None,
    #                     'author_email': commit['author']['user']['email'] if commit['author']['user'] is not None else
    #                     commit['committer']['user']['email'] if commit['committer']['user'] is not None else None,
    #                     "modified_files": modified_files
    #                 }
    #                 new_commits.append(commit_data)

    #             if new_commits:
    #                 os.remove(update_path)
    #                 with open(update_path, 'a', encoding='utf-8') as f:
    #                     f.write('[')
    #                     for i, commit in enumerate(new_commits):
    #                         json.dump(commit, f, ensure_ascii=False, indent=4)
    #                         if i < len(new_commits) - 1:
    #                             f.write(',')
    #                     f.write(']')

    #                 with open(file_path, 'r+', encoding='utf-8') as f:
    #                     existing_data = json.load(f)
    #                     existing_data.extend(new_commits)
    #                     f.seek(0)
    #                     json.dump(existing_data, f, ensure_ascii=False, indent=4)

    #             pageInfo = data['repository']['defaultBranchRef']['target']['history']['pageInfo']
    #             has_next_page = pageInfo['hasNextPage'] and has_next_page
    #             after_cursor = pageInfo['endCursor']
    #     except Exception as e:
    #         logger.error(f"Error occurred while updating commits: {e}", exc_info=True)

    def update_commits(self, last_collected_date):
        logger.info("Updating commits since last collected date")
        file_path = os.path.join(self.base_dir, f'{self.repo_name}_commits.json')
        update_path = f'{self.base_dir}/new_{self.repo_name}_commits.json'

        try:
            existing_commits = []
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    existing_commits = json.load(f)

            last_collected_date = datetime.fromisoformat(last_collected_date).strftime('%Y-%m-%d %H:%M:%S %z')

            # Get new commits since last_collected_date
            git_log_output = self.run_git_command([
                'log', '--since', last_collected_date,
                '--pretty=format:%H%x09%an%x09%ae%x09%ad%x09%s', '--date=iso'
            ])

            if not git_log_output:
                logger.info("No new commits since last collected date.")
                return

            new_commits = []
            for line in git_log_output.split('\n'):
                parts = line.strip().split('\t')
                if len(parts) >= 5:
                    commit_hash, author_name, author_email, committed_date, message = parts[:5]

                    # Check if the commit already exists
                    if any(commit['hash'] == commit_hash for commit in existing_commits):
                        continue

                    modified_files = self.get_additional_commit_details(commit_hash)

                    branches_output = self.run_git_command([
                        'branch', '--contains', commit_hash
                    ])
                    branches = [branch.strip().replace('* ', '') for branch in branches_output.splitlines()]

                    commit_data = {
                        "hash": commit_hash,
                        "author_name": author_name,
                        "author_email": author_email,
                        "committedDate": datetime.strptime(committed_date, '%Y-%m-%d %H:%M:%S %z').isoformat(),
                        "message": message,
                        "branches": branches,
                        "modified_files": modified_files,
                    }
                    new_commits.append(commit_data)

            if new_commits:
                try:
                    with open(update_path, 'w', encoding='utf-8') as f:
                        json.dump(new_commits, f, ensure_ascii=False, indent=4)

                    try:
                        temp_file_path = file_path + '.tmp'
                        combined_commits = existing_commits + new_commits
                        with open(temp_file_path, 'w', encoding='utf-8') as f:
                            json.dump(combined_commits, f, ensure_ascii=False, indent=4)

                        os.replace(temp_file_path, file_path)
                    except Exception as e:
                        logger.error(f"Error occurred while updating existing commits: {e}", exc_info=True)
                        if os.path.exists(temp_file_path):
                            os.remove(temp_file_path)
                except Exception as e:
                    logger.error(f"Error occurred while writing new commits to update file: {e}", exc_info=True)
                    if os.path.exists(update_path):
                        os.remove(update_path)  
            else:
                logger.info("No new commits to update.")

        except Exception as e:
            logger.error(f"Error occurred while updating commits: {e}", exc_info=True)


    def collect_all_issues(self):
        logger.info("Collecting all issues")
        file_path = f'{self.base_dir}/{self.repo_name}_issues.json'
        has_next_page = True
        after_cursor = None

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('[')

        try:
            first_write = True

            while has_next_page:
                data = self.get_all_instances_of_entity('issues', after_cursor=after_cursor)
                repository_id = data['repository']['id']
                issues = data['repository']['issues']['nodes']

                for issue in issues:
                    issue_data = {
                        'repository_id': repository_id,
                        'id': issue['id'],
                        'author_login': issue['author']['login'] if issue['author'] else None,
                        'author_id': issue['author']['id'] if issue['author'] else None,
                        'author_email': issue['author']['email'] if issue['author'] else None,
                        'author_name': issue['author']['name'] if issue['author'] else None,
                        "number": issue['number'],
                        "title": issue['title'],
                        "body": issue['body'],
                        "state": issue['state'],
                        "created_at": issue['createdAt'],
                        "assignees": issue['assignees']['nodes'],
                        "closed_at": issue['closedAt'],
                        "participants": issue['participants']['nodes'],
                        "state_reason": issue['stateReason'],
                        "updated_at": issue['updatedAt'],
                        'url': issue['url'],
                    }

                    with open(file_path, 'a', encoding='utf-8') as f:
                        if not first_write:
                            f.write(',')
                        else:
                            first_write = False
                        json.dump(issue_data, f, ensure_ascii=False, indent=4)

                has_next_page = data['repository']['issues']['pageInfo']['hasNextPage']
                after_cursor = data['repository']['issues']['pageInfo']['endCursor']

            # with open(file_path, 'a', encoding='utf-8') as f:
            #     f.write(']')
        except Exception as e:
            logger.error(f"Error occurred while collecting issues: {e}", exc_info=True)
        finally:
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(']')

    def update_issues(self, last_collected_date):
        file_path = f'{self.base_dir}/{self.repo_name}_issues.json'
        update_path = f'{self.base_dir}/new_{self.repo_name}_issues.json'
        has_next_page = True
        after_cursor = None

        try:
            if not os.path.exists(file_path):
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write('[]')

            new_issues = []

            while has_next_page:
                try:
                    data = self.get_all_instances_of_entity('issues', after_cursor=after_cursor)
                    repository_id = data['repository']['id']
                    issues = data['repository']['issues']['nodes']

                    for issue in issues:
                        issue_created_at = issue['createdAt']
                        if issue_created_at <= last_collected_date:
                            has_next_page = False
                            break

                        issue_data = {
                            'repository_id': repository_id,
                            'id': issue['id'],
                            'author_login': issue['author']['login'] if issue['author'] else None,
                            'author_id': issue['author']['id'] if issue['author'] else None,
                            'author_email': issue['author']['email'] if issue['author'] else None,
                            'author_name': issue['author']['name'] if issue['author'] else None,
                            "number": issue['number'],
                            "title": issue['title'],
                            "body": issue['body'],
                            "state": issue['state'],
                            "created_at": issue['createdAt'],
                            "assignees": issue['assignees']['nodes'],
                            "closed_at": issue['closedAt'],
                            "participants": issue['participants']['nodes'],
                            "state_reason": issue['stateReason'],
                            "updated_at": issue['updatedAt'],
                            'url': issue['url'],
                        }
                        new_issues.append(issue_data)

                    pageInfo = data['repository']['issues']['pageInfo']
                    has_next_page = pageInfo['hasNextPage'] or has_next_page
                    after_cursor = pageInfo['endCursor']
                except Exception as e:
                    logger.error(f"Error occurred while updating issues: {e}", exc_info=True)
                    has_next_page = False

            if new_issues:
                try:
                    with open(update_path, 'w', encoding='utf-8') as f:
                        json.dump(new_issues, f, ensure_ascii=False, indent=4)

                    try:
                        temp_file_path = file_path + '.tmp'
                        with open(file_path, 'r', encoding='utf-8') as f:
                            existing_data = json.load(f)
                        combined_data = existing_data + new_issues
                        with open(temp_file_path, 'w', encoding='utf-8') as f:
                            json.dump(combined_data, f, ensure_ascii=False, indent=4)
                        os.replace(temp_file_path, file_path)
                    except Exception as e:
                        logger.error(f"Error occurred while updating existing issues: {e}", exc_info=True)
                        if os.path.exists(temp_file_path):
                            os.remove(temp_file_path)
                except Exception as e:
                    logger.error(f"Error occurred while writing new issues to update file: {e}", exc_info=True)
                    if os.path.exists(update_path):
                        os.remove(update_path)

        except Exception as e:
            logger.error(f"Error occurred while updating issues: {e}", exc_info=True)


    def collect_all_pull_requests(self):
        logger.info('Collecting all pull requests')
        file_path = f'{self.base_dir}/{self.repo_name}_pull_requests.json'
        has_next_page = True
        after_cursor = None

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('[')

        try:
            first_write = True

            while has_next_page:
                data = self.get_all_instances_of_entity('pull_requests', after_cursor=after_cursor)
                repository_id = data['repository']['id']
                pull_requests = data['repository']['pullRequests']['nodes']

                for pull_request in pull_requests:
                    pull_request_data = {
                        'repository_id': repository_id,
                        "url": pull_request['url'],
                        'author_login': pull_request['author']['login'] if pull_request['author'] else None,
                        'author_name': pull_request['author']['name'] if pull_request['author'] else None,
                        'author_email': pull_request['author']['email'] if pull_request['author'] else None,
                        'author_id': pull_request['author']['id'] if pull_request['author'] else None,
                        "number": pull_request['number'],
                        "title": pull_request['title'],
                        "body": pull_request['body'],
                        'changed_files': pull_request['changedFiles'],
                        "state": pull_request['state'],
                        "closing_issues": pull_request['closingIssuesReferences']['nodes'] if pull_request['closingIssuesReferences'] else [],
                        'commits': pull_request['commits']['nodes'] if pull_request['commits'] else [],
                        "comments_count": pull_request['comments']['totalCount'] if pull_request['comments'] else 0,
                        "created_at": pull_request['createdAt'],
                        'files': pull_request['files']['nodes'] if pull_request['files'] else [],
                        'id': pull_request['id'],
                        "assignees": pull_request['assignees']['nodes'] if pull_request['assignees'] else [],
                        "closed_at": pull_request['closedAt'],
                        "participants": pull_request['participants']['nodes'] if pull_request['participants'] else [],
                        "updated_at": pull_request['updatedAt']
                    }

                    with open(file_path, 'a', encoding='utf-8') as f:
                        if not first_write:
                            f.write(',')
                        else:
                            first_write = False
                        json.dump(pull_request_data, f, ensure_ascii=False, indent=4)

                has_next_page = data['repository']['pullRequests']['pageInfo']['hasNextPage']
                after_cursor = data['repository']['pullRequests']['pageInfo']['endCursor']

            # with open(file_path, 'a', encoding='utf-8') as f:
            #     f.write(']')
        except Exception as e:
            logger.error(f"Error occurred while collecting pull requests: {e}", exc_info=True)
        finally:
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(']')

    def update_pull_requests(self, last_collected_date):
        file_path = f'{self.base_dir}/{self.repo_name}_pull_requests.json'
        update_path = f'{self.base_dir}/new_{self.repo_name}_pull_requests.json'
        has_next_page = True
        after_cursor = None

        try:
            if not os.path.exists(file_path):
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write('[]')

            new_pull_requests = []

            while has_next_page:
                try:
                    data = self.get_all_instances_of_entity('pull_requests', after_cursor=after_cursor)
                    repository_id = data['repository']['id']
                    pull_requests = data['repository']['pullRequests']['nodes']

                    for pull_request in pull_requests:
                        pull_request_created_at = pull_request['createdAt']
                        if last_collected_date:
                            if pull_request_created_at <= last_collected_date:
                                has_next_page = False
                                break

                        pull_request_data = {
                            'repository_id': repository_id,
                            "url": pull_request['url'],
                            'author_login': pull_request['author']['login'] if pull_request['author'] is not None else None,
                            'author_name': pull_request['author']['name'] if pull_request['author'] is not None else None,
                            'author_email': pull_request['author']['email'] if pull_request['author'] is not None else None,
                            'author_id': pull_request['author']['id'] if pull_request['author'] is not None else None,
                            "number": pull_request['number'],
                            "title": pull_request['title'],
                            "body": pull_request['body'],
                            'changed_files': pull_request['changedFiles'],
                            "state": pull_request['state'],
                            "closing_issues": pull_request['closingIssuesReferences']['nodes'],
                            'commits': pull_request['commits']['nodes'],
                            "comments_count": pull_request['comments']['totalCount'],
                            "created_at": pull_request['createdAt'],
                            'files': pull_request['files']['nodes'],
                            'id': pull_request['id'],
                            "assignees": pull_request['assignees']['nodes'],
                            "closed_at": pull_request['closedAt'],
                            "participants": pull_request['participants']['nodes'],
                            "updated_at": pull_request['updatedAt']
                        }

                        new_pull_requests.append(pull_request_data)

                    pageInfo = data['repository']['pullRequests']['pageInfo']
                    has_next_page = pageInfo['hasNextPage'] or has_next_page
                    after_cursor = pageInfo['endCursor']
                except Exception as e:
                    logger.error(f"Error occurred while updating pull requests: {e}", exc_info=True)
                    has_next_page = False

            if new_pull_requests:
                try:
                    with open(update_path, 'w', encoding='utf-8') as f:
                        json.dump(new_pull_requests, f, ensure_ascii=False, indent=4)

                    try:
                        temp_file_path = file_path + '.tmp'
                        with open(file_path, 'r', encoding='utf-8') as f:
                            existing_data = json.load(f)
                        combined_data = existing_data + new_pull_requests
                        with open(temp_file_path, 'w', encoding='utf-8') as f:
                            json.dump(combined_data, f, ensure_ascii=False, indent=4)
                        os.replace(temp_file_path, file_path)
                    except Exception as e:
                        logger.error(f"Error occurred while updating existing pull requests: {e}", exc_info=True)
                        if os.path.exists(temp_file_path):
                            os.remove(temp_file_path)
                except Exception as e:
                    logger.error(f"Error occurred while writing new pull requests to update file: {e}", exc_info=True)
                    if os.path.exists(update_path):
                        os.remove(update_path)
        except Exception as e:
            logger.error(f"Error occurred while updating pull requests: {e}", exc_info=True)    

    def collect_all_releases(self):
        logger.info('Collecting all releases')
        file_path = f'{self.base_dir}/{self.repo_name}_releases.json'
        has_next_page = True
        after_cursor = None

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('[')

        try:
            first_write = True

            while has_next_page:
                data = self.get_all_instances_of_entity('releases', after_cursor=after_cursor)
                repository_id = data['repository']['id']
                releases = data['repository']['releases']['nodes']

                for release in releases:
                    release_data = {
                        'repository_id': repository_id,
                        'author_id': release['author']['id'],
                        'author_name': release['author']['name'],
                        'author_email': release['author']['email'],
                        'author_login': release['author']['login'],
                        'is_latest': release['isLatest'],
                        'created_at': release['createdAt'],
                        "description": release['description'],
                        "id": release['id'],
                        'name': release['name'],
                        "url": release['url'],
                    }

                    with open(file_path, 'a', encoding='utf-8') as f:
                        if not first_write:
                            f.write(',')
                        else:
                            first_write = False
                        json.dump(release_data, f, ensure_ascii=False, indent=4)
                has_next_page = data['repository']['releases']['pageInfo']['hasNextPage']
                after_cursor = data['repository']['releases']['pageInfo']['endCursor']

            # with open(file_path, 'a', encoding='utf-8') as f:
            #     f.write(']')
        except Exception as e:
            logger.error(f"Error occurred while collecting releases: {e}", exc_info=True)
        finally:
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(']')

    def collect_all_projects(self):
        logger.info('Collecting all projects')
        file_path = f'{self.base_dir}/{self.repo_name}_projects.json'
        has_next_page = True
        after_cursor = None

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('[')

        try:
            first_write = True

            while has_next_page:
                data = self.get_all_instances_of_entity('projects', after_cursor=after_cursor)
                repository_id = data['repository']['id']
                projects = data['repository']['projects']['nodes']

                for project in projects:
                    project_data = {
                        'repository_id': repository_id,
                        'creator_id': project['creator']['id'],
                        'creator_name': project['creator']['name'],
                        'creator_email': project['creator']['email'],
                        'creator_login': project['creator']['login'],
                        "id": project['id'],
                        'name': project['name'],
                        'body': project['body'],
                        'number': project['number'],
                        'state': project['state'],
                        'done_percentage': project['progress']['donePercentage'],
                        'in_progress_percentage': project['progress']['inProgressPercentage'],
                        'todo_percentage': project['progress']['todoPercentage'],
                        'url': project['url'],
                        'created_at': project['createdAt']
                    }

                    with open(file_path, 'a', encoding='utf-8') as f:
                        if not first_write:
                            f.write(',')
                        else:
                            first_write = False
                        json.dump(project_data, f, ensure_ascii=False, indent=4)
                has_next_page = data['repository']['projects']['pageInfo']['hasNextPage']
                after_cursor = data['repository']['projects']['pageInfo']['endCursor']

            # with open(file_path, 'a', encoding='utf-8') as f:
            #     f.write(']')
        except Exception as e:
            logger.error(f"Error occurred while collecting projects: {e}", exc_info=True)
        finally:
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(']')

    def collect_all_forks(self):
        logger.info('Collecting all forks')
        file_path = f'{self.base_dir}/{self.repo_name}_forks.json'
        has_next_page = True
        after_cursor = None

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('[')

        try:
            first_write = True

            while has_next_page:
                data = self.get_all_instances_of_entity('forks', after_cursor=after_cursor)
                repository_id = data['repository']['id']
                forks = data['repository']['forks']['nodes']

                for fork in forks:
                    fork_data = {
                        'repository_id': repository_id,
                        "id": fork['id'],
                        'name': fork['name'],
                        'url': fork['url'],
                    }

                    with open(file_path, 'a', encoding='utf-8') as f:
                        if not first_write:
                            f.write(',')
                        else:
                            first_write = False
                        json.dump(fork_data, f, ensure_ascii=False, indent=4)
                has_next_page = data['repository']['forks']['pageInfo']['hasNextPage']
                after_cursor = data['repository']['forks']['pageInfo']['endCursor']

            # with open(file_path, 'a', encoding='utf-8') as f:
            #     f.write(']')
        except Exception as e:
            logger.error(f"Error occurred while collecting forks: {e}", exc_info=True)
        finally:
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(']')

    def collect_all_languages(self):
        logger.info('Collecting all languages')
        file_path = f'{self.base_dir}/{self.repo_name}_languages.json'
        has_next_page = True
        after_cursor = None

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('[')

        try:
            first_write = True

            while has_next_page:
                data = self.get_all_instances_of_entity('languages', after_cursor=after_cursor)
                repository_id = data['repository']['id']
                languages = data['repository']['languages']['nodes']

                for language in languages:
                    language_data = {
                        'repository_id': repository_id,
                        "id": language['id'],
                        'name': language['name'],
                        'color': language['color'],
                    }

                    with open(file_path, 'a', encoding='utf-8') as f:
                        if not first_write:
                            f.write(',')
                        else:
                            first_write = False
                        json.dump(language_data, f, ensure_ascii=False, indent=4)
                has_next_page = data['repository']['languages']['pageInfo']['hasNextPage']
                after_cursor = data['repository']['languages']['pageInfo']['endCursor']

            # with open(file_path, 'a', encoding='utf-8') as f:
            #     f.write(']')
        except Exception as e:
            logger.error(f"Error occurred while collecting languages: {e}", exc_info=True)
        finally:
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(']')

    def update_releases(self, last_collected_date):
        file_path = f'{self.base_dir}/{self.repo_name}_releases.json'
        update_path = f'{self.base_dir}/new_{self.repo_name}_releases.json'
        has_next_page = True
        after_cursor = None

        try:
            if not os.path.exists(file_path):
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write('[]')

            new_releases = []

            while has_next_page:
                try:
                    data = self.get_all_instances_of_entity('releases', after_cursor=after_cursor)
                    repository_id = data['repository']['id']
                    releases = data['repository']['releases']['nodes']

                    for release in releases:
                        release_created_at = release['createdAt']
                        if release_created_at <= last_collected_date:
                            has_next_page = False
                            break

                        release_data = {
                            'repository_id': repository_id,
                            "url": release['url'],
                            'author_login': release['author']['login'],
                            'author_name': release['author']['name'],
                            'author_email': release['author']['email'],
                            'author_id': release['author']['id'],
                            "number": release['number'],
                            "title": release['title'],
                            "body": release['body'],
                            'changed_files': release['changedFiles'],
                            "state": release['state'],
                            "closing_issues": release['closingIssuesReferences']['nodes'],
                            'commits': release['commits']['nodes'],
                            "comments_count": release['comments']['totalCount'],
                            "created_at": release['createdAt'],
                            'files': release['files']['nodes'],
                            'id': release['id'],
                            "assignees": release['assignees']['nodes'],
                            "closed_at": release['closedAt'],
                            "participants": release['participants']['nodes'],
                            "updated_at": release['updatedAt']
                        }

                        new_releases.append(release_data)

                    pageInfo = data['repository']['releases']['pageInfo']
                    has_next_page = pageInfo['hasNextPage'] or has_next_page
                    after_cursor = pageInfo['endCursor']
                except Exception as e:
                    logger.error(f"Error occurred while updating releases: {e}", exc_info=True)
                    has_next_page = False

            if new_releases:
                try:
                    with open(update_path, 'w', encoding='utf-8') as f:
                        json.dump(new_releases, f, ensure_ascii=False, indent=4)

                    try:
                        temp_file_path = file_path + '.tmp'
                        with open(file_path, 'r', encoding='utf-8') as f:
                            existing_data = json.load(f)
                        combined_data = existing_data + new_releases
                        with open(temp_file_path, 'w', encoding='utf-8') as f:
                            json.dump(combined_data, f, ensure_ascii=False, indent=4)
                        os.replace(temp_file_path, file_path)
                    except Exception as e:
                        logger.error(f"Error occurred while updating existing releases: {e}", exc_info=True)
                        if os.path.exists(temp_file_path):
                            os.remove(temp_file_path)
                except Exception as e:
                    logger.error(f"Error occurred while writing new releases to update file: {e}", exc_info=True)
                    if os.path.exists(update_path):
                        os.remove(update_path)
        except Exception as e:
            logger.error(f"Error occurred while updating releases: {e}", exc_info=True)

    def update_projects(self, last_collected_date):
        file_path = f'{self.base_dir}/{self.repo_name}_projects.json'
        update_path = f'{self.base_dir}/new_{self.repo_name}_projects.json'
        has_next_page = True
        after_cursor = None

        try:
            if not os.path.exists(file_path):
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write('[]')

            new_projects = []

            while has_next_page:
                try:
                    data = self.get_all_instances_of_entity('projects', after_cursor=after_cursor)
                    repository_id = data['repository']['id']
                    projects = data['repository']['projects']['nodes']

                    for project in projects:
                        project_created_at = project['createdAt']
                        if project_created_at <= last_collected_date:
                            has_next_page = False
                            break

                        project_data = {
                            'repository_id': repository_id,
                            'creator_id': project['creator']['id'],
                            'creator_name': project['creator']['name'],
                            'creator_email': project['creator']['email'],
                            'creator_login': project['creator']['login'],
                            "id": project['id'],
                            'name': project['name'],
                            'body': project['body'],
                            'number': project['number'],
                            'state': project['state'],
                            'done_percentage': project['progress']['donePercentage'],
                            'in_progress_percentage': project['progress']['inProgressPercentage'],
                            'todo_percentage': project['progress']['todoPercentage'],
                            'url': project['url'],
                            'created_at': project['createdAt']
                        }

                        new_projects.append(project_data)

                    pageInfo = data['repository']['projects']['pageInfo']
                    has_next_page = pageInfo['hasNextPage'] or has_next_page
                    after_cursor = pageInfo['endCursor']
                except Exception as e:
                    logger.error(f"Error occurred while updating projects: {e}", exc_info=True)
                    has_next_page = False

            if new_projects:
                try:
                    with open(update_path, 'w', encoding='utf-8') as f:
                        json.dump(new_projects, f, ensure_ascii=False, indent=4)

                    try:
                        temp_file_path = file_path + '.tmp'
                        with open(file_path, 'r', encoding='utf-8') as f:
                            existing_data = json.load(f)
                        combined_data = existing_data + new_projects
                        with open(temp_file_path, 'w', encoding='utf-8') as f:
                            json.dump(combined_data, f, ensure_ascii=False, indent=4)
                        os.replace(temp_file_path, file_path)
                    except Exception as e:
                        logger.error(f"Error occurred while updating existing projects: {e}", exc_info=True)
                        if os.path.exists(temp_file_path):
                            os.remove(temp_file_path)
                except Exception as e:
                    logger.error(f"Error occurred while writing new projects to update file: {e}", exc_info=True)
                    if os.path.exists(update_path):
                        os.remove(update_path)
        except Exception as e:
            logger.error(f"Error occurred while updating projects: {e}", exc_info=True)

    def collect_all_collaborators(self):
        logger.info('Collecting all collaborators')
        file_path = f'{self.base_dir}/{self.repo_name}_collaborators.json'
        has_next_page = True
        after_cursor = None

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('[')

        try:
            first_write = True

            while has_next_page:
                data = self.get_all_instances_of_entity('collaborators', after_cursor=after_cursor)
                repository_id = data['repository']['id']
                collaborators_edges = data['repository']['collaborators']['edges']
                # collaborators = data['repository']['collaborators']['nodes']

                for edge in collaborators_edges:
                # for collaborator in collaborators:
                    collaborator = edge['node']
                    permission = edge['permission'] 

                    collaborator_data = {
                        'repository_id': repository_id,
                        'id': collaborator['id'],
                        'login': collaborator['login'],
                        'name': collaborator['name'],
                        'email': collaborator['email'],
                        'permission': permission,
                    }

                    with open(file_path, 'a', encoding='utf-8') as f:
                        if not first_write:
                            f.write(',')
                        else:
                            first_write = False
                        json.dump(collaborator_data, f, ensure_ascii=False, indent=4)
                has_next_page = data['repository']['collaborators']['pageInfo']['hasNextPage']
                after_cursor = data['repository']['collaborators']['pageInfo']['endCursor']

        except Exception as e:
            logger.error(f"Error occurred while collecting collaborators: {e}", exc_info=True)
        finally:
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(']')



    def collect_data(self):
        logger.info("Collecting repository data")
        first_run = False

        logger.info("Collecting COMMIT data")
        logger.info("Error in line 1")
        commit_path = f'{self.base_dir}/{self.repo_name}_commits.json'
        commits = []
        if os.path.exists(commit_path):
            logger.info("Error in line 2")
            with open(commit_path, 'r', encoding='utf-8') as f:
                try:
                    logger.info("Error in line 3")
                    commits = json.load(f)
                # except json.JSONDecodeError:
                except Exception as e:
                    logger.info("Error in line 4")
                    logger.error(f"Exception occurred: {e}")
                    commits = []
        logger.info("Error in line 5")
        if len(commits) != 0:
            logger.info("Error in line 6")
            last_collected_date = max(commit['committedDate'] for commit in commits)
        else:
            logger.info("Error in line 7")
            last_collected_date = None
        if last_collected_date:
            logger.info("Error in line 8")
            self.update_commits(last_collected_date)
        else:
            logger.info("Error in line 9")
            self.collect_all_commits()
            first_run = True

        logger.info("Collecting REPOSITORY data")
        repository_path = f'{self.base_dir}/{self.repo_name}_repositories.json'
        if not os.path.exists(repository_path):
            # os.remove(repository_path)
            self.get_repository_data()

        logger.info("Collecting COLLABORATOR data")
        collaborator_path = f'{self.base_dir}/{self.repo_name}_collaborators.json'
        if not os.path.exists(collaborator_path):
            # os.remove(collaborator_path)
            self.collect_all_collaborators()

        logger.info("Collecting RELEASE data")
        release_path = f'{self.base_dir}/{self.repo_name}_releases.json'
        releases = []
        if os.path.exists(release_path):
            with open(release_path, 'r', encoding='utf-8') as f:
                try:
                    releases = json.load(f)
                except json.JSONDecodeError:
                    releases = []
        if len(releases) != 0:
            last_collected_date = max(release['created_at'] for release in releases)
        else:
            last_collected_date = None
        if last_collected_date:
            self.update_releases(last_collected_date)
        else:
            self.collect_all_releases()
            first_run = True

        logger.info("Collecting PROGRAMMING LANGUAGE data")
        language_path = f'{self.base_dir}/{self.repo_name}_languages.json'
        if not os.path.exists(language_path):
            # os.remove(language_path)
            self.collect_all_languages()

        logger.info("Collecting FORK data")
        fork_path = f'{self.base_dir}/{self.repo_name}_forks.json'
        if not os.path.exists(fork_path):
            # os.remove(fork_path)
            self.collect_all_forks()

        logger.info("Collecting PROJECT data")
        project_path = f'{self.base_dir}/{self.repo_name}_projects.json'
        projects = []
        if os.path.exists(project_path):
            with open(project_path, 'r', encoding='utf-8') as f:
                try:
                    projects = json.load(f)
                except json.JSONDecodeError:
                    projects = []
        if len(projects) != 0:
            last_collected_date = max(project['created_at'] for project in projects)
        else:
            last_collected_date = None
        if last_collected_date:
            self.update_projects(last_collected_date)
        else:
            self.collect_all_projects()
            first_run = True

        logger.info("Collecting ISSUE data")
        issue_path = f'{self.base_dir}/{self.repo_name}_issues.json'
        issues = []
        if os.path.exists(issue_path):
            with open(issue_path, 'r', encoding='utf-8') as f:
                try:
                    issues = json.load(f)
                except json.JSONDecodeError:
                    issues = []
        if len(issues) != 0:
            last_collected_date = max(issue['created_at'] for issue in issues)
        else:
            last_collected_date = None
        if last_collected_date:
            self.update_issues(last_collected_date)
        else:
            self.collect_all_issues()
            first_run = True

        logger.info("Collecting PULL REQUEST data")
        pull_request_path = f'{self.base_dir}/{self.repo_name}_pull_requests.json'
        pull_requests = []
        if os.path.exists(pull_request_path):
            with open(pull_request_path, 'r', encoding='utf-8') as f:
                try:
                    pull_requests = json.load(f)
                except json.JSONDecodeError:
                    pull_requests = []
            if len(pull_requests) != 0:
                last_collected_date = max(pull_request['created_at'] for pull_request in pull_requests)
            else:
                last_collected_date = None
            # if last_collected_date:
            self.update_pull_requests(last_collected_date)
        else:
            self.collect_all_pull_requests()
            first_run = True

        print("Data collection complete")
        return first_run
