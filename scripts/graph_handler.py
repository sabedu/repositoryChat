import networkx as nx
import json
from logging import getLogger

logger = getLogger(__name__)


class DataHandler:
    def __init__(self, file_path):
        self.file_path = file_path

    def load_data(self):
        logger.info('Loading data from {}'.format(self.file_path))
        with open(self.file_path, 'r') as file:
            return json.load(file)
    
    def save_data(self, data):
        logger.info('Saving data to {}'.format(self.file_path))
        with open(self.file_path, 'w') as file:
            json.dump(data, file, indent=4)


def remove_single_quotes(text):
    result = text.replace("'", "")
    result = '"' + result + '"'
    return result


class GraphHandler:
    def __init__(self):
        self.G = nx.MultiDiGraph()

    def save_graph(self, file_path):
        logger.info('Saving graph')
        nx.write_graphml(self.G, file_path)

    def add_collaborator_nodes_and_edges(self, collaborators):
        logger.info('Adding collaborator nodes and edges')
        for collaborator in collaborators:
            self.G.add_node(collaborator['id'], type='User', name=collaborator['name'], login=collaborator['login'],
                            email=collaborator['email'], permission=collaborator['permission'], id=collaborator['id'])

    def add_repository_nodes(self, repositories, collaborators):
        logger.info('Adding repositories nodes')
        collaborator_dict = {collaborator['id']: collaborator for collaborator in collaborators}
        for repository in repositories:
            self.G.add_node(repository['id'], type='Repository', name=repository['name'],
                            description=repository['description'],
                            url=repository['url'], stars=repository['stars'], visibility=repository['visibility'],
                            forksCount=repository['forksCount'], isTemplate=repository['isTemplate'],
                            primaryLanguage=repository['primaryLanguage'])

            owner_login = repository['owner_login']
            owner_name = repository['owner_name'] if repository['owner_name'] is not None else owner_login
            owner_email = repository['owner_email'] if repository['owner_email'] is not None else ''
            owner_id = repository['owner_id']

            if owner_id in collaborator_dict:
                collaborator = collaborator_dict[owner_id]
                if not self.G.has_node(owner_id):
                    self.G.add_node(
                        owner_id,
                        type='User',
                        name=collaborator['name'],
                        login=collaborator['login'],
                        email=collaborator['email'],
                        id=owner_id
                    )
            else:
                if all([owner_id, owner_login]):
                    if not self.G.has_node(owner_id):
                        self.G.add_node(
                            owner_id,
                            type='User',
                            name=owner_name,
                            login=owner_login,
                            email=owner_email,
                            id=owner_id
                        )

                        collaborators.append({
                            'id': owner_id,
                            'name': owner_name,
                            'login': owner_login,
                            'email': owner_email,
                            'permission': 'Admin'
                        })

            if owner_id is not None:
                self.G.add_edge(owner_id, repository['id'], relation='owns')

            for branch in repository['branches']['nodes']:
                self.G.add_node(branch['name'], type='Branch', name=branch['name'])
                self.G.add_edge(branch['name'], repository['id'], relation='branch_of')
        return collaborators

    def add_release_nodes_and_edges(self, releases, collaborators):
        logger.info('Adding releases nodes and edges')

        collaborator_dict = {collaborator['id']: collaborator for collaborator in collaborators}

        for release in releases:
            self.G.add_node(
                release['id'],
                type='Release',
                name=release['name'],
                description=release['description'],
                url=release['url'],
                createdAt=release['created_at'],
                isLatest=release['is_latest']
            )

            author_id = release['author_id']
            author_login = release.get('author_login')
            author_name = release.get('author_name')
            author_email = release.get('author_email', '')

            if author_id in collaborator_dict:
                collaborator = collaborator_dict[author_id]
                if not self.G.has_node(author_id):
                    self.G.add_node(
                        author_id,
                        type='User',
                        name=collaborator['name'],
                        login=collaborator['login'],
                        email=collaborator['email'],
                        id=author_id
                    )
            else:
                if all([author_id, author_login]):
                    if not self.G.has_node(author_id):
                        self.G.add_node(
                            author_id,
                            type='User',
                            name=author_name,
                            login=author_login,
                            email=author_email,
                            id=author_id
                        )

                        collaborators.append({
                            'id': author_id,
                            'name': author_name,
                            'login': author_login,
                            'email': author_email,
                            'permission': 'author'
                        })

            if author_id is not None:
                self.G.add_edge(author_id, release['id'], relation='author')
                # self.G.add_edge(author_id, release['repository_id'], relation='contributes_to')

            self.G.add_edge(release['id'], release['repository_id'], relation='release_of')

        return collaborators

    def add_language_nodes_and_edges(self, languages):
        logger.info('Adding languages nodes and edges')
        for language in languages:
            self.G.add_node(language['id'], type='Language', name=language['name'], color=language['color'])
            self.G.add_edge(language['id'], language['repository_id'], relation='language_of')

    def add_project_nodes_and_edges(self, projects, collaborators):
        logger.info('Adding projects nodes and edges')
        collaborator_dict = {collaborator['id']: collaborator for collaborator in collaborators}
        for project in projects:
            self.G.add_node(
                project['id'],
                type='Project',
                name=project['name'],
                url=project['url'],
                createdAt=project['created_at'],
                donePercentage=project['done_percentage'],
                inProgressPercentage=project['in_progress_percentage'],
                body=project['body'],
                todoPercentage=project['todo_percentage'],
                state=project['state'],
                number=project['number']
            )
            creator_id = project['creator_id']
            creator_login = project.get('creator_login')
            creator_name = project.get('creator_name')
            creator_email = project.get('creator_email', '')
            if creator_id in collaborator_dict:
                collaborator = collaborator_dict[creator_id]
                if not self.G.has_node(creator_id):
                    self.G.add_node(
                        creator_id,
                        type='User',
                        name=collaborator['name'],
                        login=collaborator['login'],
                        email=collaborator['email'],
                        id=creator_id
                    )
            else:
                if all([creator_id, creator_login]):
                    if not self.G.has_node(creator_id):
                        self.G.add_node(
                            creator_id,
                            type='User',
                            name=creator_name,
                            login=creator_login,
                            email=creator_email,
                            id=creator_id
                        )
                        collaborators.append({
                            'id': creator_id,
                            'name': creator_name,
                            'login': creator_login,
                            'email': creator_email,
                            'permission': 'creator'
                        })

            if creator_id is not None:
                self.G.add_edge(creator_id, project['id'], relation='creates')
            self.G.add_edge(project['id'], project['repository_id'], relation='project_of')

        return collaborators


    def add_fork_nodes_and_edges(self, forks):
        logger.info('Adding forks nodes and edges')
        for fork in forks:
            self.G.add_node(fork['id'], type='Fork', name=fork['name'], url=fork['url'])
            self.G.add_edge(fork['id'], fork['repository_id'], relation='fork_of')

    def add_commit_nodes_and_edges(self, commits, collaborators, repository_id):
        logger.info('Adding commit nodes and edges')
        # collaborator_dict = {(collaborator['name'], collaborator['email']): collaborator for collaborator in collaborators}
        collaborator_dict = {collaborator['name']: collaborator for collaborator in collaborators}
        collaborator_login_dict = {collaborator['login']: collaborator for collaborator in collaborators}
        for commit in commits:
            commit_hash = commit['hash']
            message = remove_single_quotes(commit['message'])
            committed_date = commit['committedDate']
            author_name = commit['author_name']
            author_email = commit['author_email'] if commit['author_email'] is not None else ''
            # author_key = (author_name, author_email)
            if author_name in collaborator_dict or author_name in collaborator_login_dict:
                collaborator = collaborator_dict.get(author_name) or collaborator_login_dict.get(author_name)
                author_id = collaborator['id']
                if not self.G.has_node(author_id):
                    self.G.add_node(
                        author_id,
                        type='User',
                        name=collaborator['name'],
                        login=collaborator['login'],
                        email=collaborator['email'],
                        id=author_id
                    )
            else:
                author_id = f"{author_name}<{author_email}>"
                if not self.G.has_node(author_id):
                    self.G.add_node(author_id, type='User', name=author_name, email=author_email, id=author_id)
            self.G.add_node(commit_hash, type='Commit', hash=commit_hash, message=message, committedDate=committed_date)
            self.G.add_edge(author_id, commit_hash, relation='author')
            self.G.add_edge(author_id, repository_id, relation='contributes_to')
            branches = commit['branches']
            for branch in branches:
                self.G.add_node(branch, type='Branch', name=branch)
                self.G.add_edge(commit_hash, branch, relation="committed_to")
            for file in commit.get('modified_files', []):
                file['path'] = file['path']
                file['filename'] = file['filename']
                file_id = file['filename']
                self.G.add_node(file_id, type='File', path=file['path'], name=file['filename'])
                self.G.add_edge(
                    commit_hash,
                    file_id,
                    relation='changed',
                    changeType=file['change_type'],
                    additions=file['additions'],
                    deletions=file['deletions'],
                    patch=file['diff']
                )
            for parent in commit.get('parents', []):
                parent_id = parent['oid']
                self.G.add_edge(parent_id, commit_hash, relation='parent_of')

            


    def add_issue_nodes_and_edges(self, issues, collaborators):
        logger.info('Adding issue nodes and edges')
        collaborator_dict = {collaborator['id']: collaborator for collaborator in collaborators}
        for issue in issues:
            url = issue['url']
            issue_id = issue['number']
            assignees = issue['assignees']
            participants = issue['participants']
            number = issue['number']
            title = remove_single_quotes(issue['title'])
            body = remove_single_quotes(issue['body'])
            state = issue['state'].lower()
            created_at = issue['created_at']
            closed_at = issue['closed_at']
            self.G.add_node(
                issue_id,
                type='Issue',
                number=number,
                url=url,
                title=title,
                body=body,
                state=state,
                createdAt=created_at,
                closedAt=closed_at
            )
            repository_id = issue['repository_id']
            author_id = issue['author_id']
            author_name = issue['author_name']
            author_login = issue['author_login']
            author_email = issue['author_email'] if issue['author_email'] is not None else ''
            if author_id is not None:
                if author_id in collaborator_dict:
                    collaborator = collaborator_dict[author_id]
                    if not self.G.has_node(author_id):
                        self.G.add_node(
                            author_id,
                            type='User',
                            name=collaborator['name'],
                            login=collaborator['login'],
                            email=collaborator['email'],
                            id=author_id
                        )
                else:
                    if all([author_id, author_login]):
                        if not self.G.has_node(author_id):
                            self.G.add_node(
                                author_id,
                                type='User',
                                name=author_name,
                                login=author_login,
                                email=author_email,
                                id=author_id
                            )

                            collaborators.append({
                                'id': author_id,
                                'name': author_name,
                                'login': author_login,
                                'email': author_email,
                                'permission': 'author'
                            })

                self.G.add_edge(author_id, issue_id, relation='creates')
                # self.G.add_edge(author_id, repository_id, relation='contributes_to')
            for assignee in assignees:
                assignee_id = assignee['id']
                assignee_name = assignee['name']
                assignee_login = assignee['login']
                assignee_email = assignee['email'] if assignee['email'] is not None else ''
                if assignee_id is not None:
                    if assignee_id in collaborator_dict:
                        collaborator = collaborator_dict[assignee_id]
                        if not self.G.has_node(assignee_id):
                            self.G.add_node(
                                assignee_id,
                                type='User',
                                name=collaborator['name'],
                                login=collaborator['login'],
                                email=collaborator['email'],
                                id=assignee_id
                            )
                    else:
                        if all([assignee_id, assignee_login]):
                            if not self.G.has_node(assignee_id):
                                self.G.add_node(
                                    assignee_id,
                                    type='User',
                                    name=assignee_name,
                                    login=assignee_login,
                                    email=assignee_email,
                                    id=assignee_id
                                )

                                collaborators.append({
                                    'id': assignee_id,
                                    'name': assignee_name,
                                    'login': assignee_login,
                                    'email': assignee_email,
                                    'permission': 'assignee'
                                })

                    self.G.add_edge(assignee_id, issue_id, relation='assigned')
                    # self.G.add_edge(assignee_id, repository_id, relation='contributes_to')
            for participant in participants:
                participant_id = participant['id']
                participant_name = participant['name']
                participant_login = participant['login']
                participant_email = participant['email'] if participant['email'] is not None else ''
                if participant_id is not None:
                    if participant_id in collaborator_dict:
                        collaborator = collaborator_dict[participant_id]
                        if not self.G.has_node(participant_id):
                            self.G.add_node(
                                participant_id,
                                type='User',
                                name=collaborator['name'],
                                login=collaborator['login'],
                                email=collaborator['email'],
                                id=participant_id
                            )
                    else:
                        if all([participant_id, participant_login]):
                            if not self.G.has_node(participant_id):
                                self.G.add_node(
                                    participant_id,
                                    type='User',
                                    name=participant_name,
                                    login=participant_login,
                                    email=participant_email,
                                    id=participant_id
                                )

                                collaborators.append({
                                    'id': participant_id,
                                    'name': participant_name,
                                    'login': participant_login,
                                    'email': participant_email,
                                    'permission': 'participant'
                                })

                    self.G.add_edge(participant_id, issue_id, relation='participates_in')
                    # self.G.add_edge(participant_id, repository_id, relation='contributes_to')
        return collaborators


    def add_pull_request_nodes_and_edges(self, pull_requests, collaborators, issues):
        logger.info('Adding pull request nodes and edges')
        collaborator_dict = {collaborator['id']: collaborator for collaborator in collaborators}
        issues_dict = {issue['id']: issue for issue in issues}
        for pull_request in pull_requests:
            url = pull_request['url']
            pull_request_id = pull_request['id']
            number = pull_request['number']
            changed_files = pull_request['changed_files']
            title = pull_request['title']
            body = remove_single_quotes(pull_request['body'])
            state = pull_request['state'].lower()
            created_at = pull_request['created_at']
            closed_at = pull_request['closed_at']
            updated_at = pull_request['updated_at']
            files = pull_request.get('files', [])
            comments_count = pull_request['comments_count']
            self.G.add_node(
                pull_request_id,
                type='PullRequest',
                number=number,
                url=url,
                title=title,
                commentsCount=comments_count,
                body=body,
                state=state,
                updatedAt=updated_at,
                createdAt=created_at,
                closedAt=closed_at,
                changedFiles=changed_files
            )
            repository_id = pull_request.get('repository_id', 'defaultRepositoryID==')
            if files is not None:
                for file in files:
                    file_name = file['path'].split('/')[-1]
                    file['filename'] = file_name.split('/')[-1]
                    file_id = file['filename']
                    self.G.add_node(file_id, type='File', path=file['path'], name=file['filename'])
                    self.G.add_edge(pull_request_id, file_id, relation='changed')
            author_id = pull_request.get('author_id', 'defaultAuthorId=')
            author_name = pull_request['author_name']
            author_login = pull_request['author_login']
            author_email = pull_request['author_email'] if pull_request['author_email'] is not None else ''
            if all([author_id, author_login]):
                if author_id in collaborator_dict:
                    collaborator = collaborator_dict[author_id]
                    if not self.G.has_node(author_id):
                        self.G.add_node(
                            author_id,
                            type='User',
                            name=collaborator['name'],
                            login=collaborator['login'],
                            email=collaborator['email'],
                            id=author_id
                        )
                else:
                    if not self.G.has_node(author_id):
                        self.G.add_node(
                            author_id,
                            type='User',
                            name=author_name,
                            login=author_login,
                            email=author_email,
                            id=author_id
                        )

                        collaborators.append({
                            'id': author_id,
                            'name': author_name,
                            'login': author_login,
                            'email': author_email,
                            'permission': 'author'
                        })

                self.G.add_edge(author_id, pull_request_id, relation='creates')
                # self.G.add_edge(author_id, repository_id, relation='contributes_to')
            for assignee in pull_request['assignees']:
                assignee_id = assignee['id']
                assignee_name = assignee['name']
                assignee_login = assignee['login']
                assignee_email = assignee['email'] if assignee['email'] is not None else ''
                if assignee_id is not None:
                    if assignee_id in collaborator_dict:
                        collaborator = collaborator_dict[assignee_id]
                        if not self.G.has_node(assignee_id):
                            self.G.add_node(
                                assignee_id,
                                type='User',
                                name=collaborator['name'],
                                login=collaborator['login'],
                                email=collaborator['email'],
                                id=assignee_id
                            )
                    else:
                        if not self.G.has_node(assignee_id):
                            self.G.add_node(
                                assignee_id,
                                type='User',
                                name=assignee_name,
                                login=assignee_login,
                                email=assignee_email,
                                id=assignee_id
                            )
                            collaborators.append({
                                'id': assignee_id,
                                'name': assignee_name,
                                'login': assignee_login,
                                'email': assignee_email,
                                'permission': 'assignee'
                            })

                    self.G.add_edge(assignee_id, pull_request_id, relation='reviews')
                    # self.G.add_edge(assignee_id, repository_id, relation="contributes_to")
            for participant in pull_request["participants"]:
                participant_id = participant['id']
                participant_name = participant['name']
                participant_login = participant['login']
                participant_email = participant['email'] if participant['email'] is not None else ''
                if participant_id is not None:
                    if participant_id in collaborator_dict:
                        collaborator = collaborator_dict[participant_id]
                        if not self.G.has_node(participant_id):
                            self.G.add_node(
                                participant_id,
                                type='User',
                                name=collaborator['name'],
                                login=collaborator['login'],
                                email=collaborator['email'],
                                id=participant_id
                            )
                    else:
                        if not self.G.has_node(participant_id):
                            self.G.add_node(
                                participant_id,
                                type='User',
                                name=participant_name,
                                login=participant_login,
                                email=participant_email,
                                id=participant_id
                            )
                            collaborators.append({
                                'id': participant_id,
                                'name': participant_name,
                                'login': participant_login,
                                'email': participant_email,
                                'permission': 'participant'
                            })

                    self.G.add_edge(participant_id, pull_request_id, relation='participates_in')
                    # self.G.add_edge(participant_id, repository_id, relation="contributes_to")
            for issue in pull_request['closing_issues']:
                issue_id = issue['number']
                if issue_id in issues_dict:
                    issue = issues_dict[issue_id]
                    if not self.G.has_node(issue_id):
                        self.G.add_node(
                            issue_id,
                            type='Issue',
                            number=issue['number'],
                            url=issue['url'],
                            title=issue['title'],
                            body=issue['body'],
                            state=issue['state'],
                            createdAt=issue['created_at'],
                            closedAt=issue['closed_at']
                        )
                # if self.G.has_node(issue_id):
                self.G.add_edge(pull_request_id, issue_id, relation='closed')
            # for commit in pull_request['commits']:
            #     commit_hash = commit['commit']['oid']
            #     # self.G.add_node(commit_hash, type='Commit')
            #     self.G.add_edge(commit_hash, pull_request_id, relation='commit_in')
        return collaborators


    def add_bic_relationships(self, bics):
        logger.info('Adding bic relationships')
        for bic in bics:
            number = int(bic["Number"])
            fixing_commits = bic["FixingCommit"]
            inducing_commits = bic["InducingCommit"]
            impacted_files = bic["ImpactedFiles"]

            for fixing_commit in fixing_commits:
                if self.G.has_node(fixing_commit):
                    self.G.add_edge(fixing_commit, number, relation='fixed')

            for inducing_commit in inducing_commits:
                if self.G.has_node(inducing_commit):
                    self.G.add_edge(inducing_commit, number, relation='introduced')

            for impacted_file in impacted_files:
                if self.G.has_node(impacted_file):
                    self.G.add_edge(number, impacted_file, relation='impacted')

    def add_commit_pull_request_edges(self, pull_requests):
        logger.info('Adding closed in relationship between pull request nodes and commit nodes')
        for pull_request in pull_requests:
            pull_request_id = pull_request['id']
            pr_commits = pull_request['commits']
            # if self.G.has_node(pull_request_id):
            for commit in pr_commits:
                commit_hash = commit['commit']['oid']
                # if self.G.has_node(commit_hash):
                self.G.add_edge(commit_hash, pull_request_id, relation='closed_in')


    def add_nodes_and_edges(self, repositories, collaborators, releases, languages, projects, forks, commits, issues,
                            pull_requests):
        logger.info('Adding all nodes and edges')
        repository_id = repositories[0]['id']
        self.add_collaborator_nodes_and_edges(collaborators)
        collaborators = self.add_repository_nodes(repositories, collaborators)
        collaborators = self.add_release_nodes_and_edges(releases, collaborators)
        self.add_language_nodes_and_edges(languages)
        collaborators = self.add_project_nodes_and_edges(projects, collaborators)
        self.add_fork_nodes_and_edges(forks)
        collaborators = self.add_issue_nodes_and_edges(issues, collaborators)
        collaborators = self.add_pull_request_nodes_and_edges(pull_requests, collaborators, issues)
        self.add_commit_nodes_and_edges(commits, collaborators, repository_id)
        self.add_commit_pull_request_edges(pull_requests)
        logger.info('All nodes and edges added')
        return collaborators
