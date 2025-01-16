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

    def get_additional_commit_details(self, commit_sha):
        logger.info(f"Collecting details for commit {commit_sha}")
        try:
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

        logger.info("Collecting COMMIT data")
        commit_path = f'{self.base_dir}/{self.repo_name}_commits.json'
        commits = []
        if os.path.exists(commit_path):
            with open(commit_path, 'r', encoding='utf-8') as f:
                try:
                    commits = json.load(f)
                except Exception as e:
                    logger.error(f"Exception occurred: {e}")
                    commits = []
        if len(commits) != 0:
            last_collected_date = max(commit['committedDate'] for commit in commits)
        else:
            last_collected_date = None
        if last_collected_date:
            self.update_commits(last_collected_date)
        else:
            self.collect_all_commits()

        logger.info("Collecting REPOSITORY data")
        repository_path = f'{self.base_dir}/{self.repo_name}_repositories.json'
        if not os.path.exists(repository_path):
            self.get_repository_data()

        logger.info("Collecting COLLABORATOR data")
        collaborator_path = f'{self.base_dir}/{self.repo_name}_collaborators.json'
        if not os.path.exists(collaborator_path):
            self.collect_all_collaborators()

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

        print("Data collection complete")
