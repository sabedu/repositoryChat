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

    def add_nodes_and_edges(self, repositories, collaborators, commits, issues):
        logger.info('Adding all nodes and edges')
        repository_id = repositories[0]['id']
        self.add_collaborator_nodes_and_edges(collaborators)
        collaborators = self.add_repository_nodes(repositories, collaborators)
        collaborators = self.add_issue_nodes_and_edges(issues, collaborators)
        self.add_commit_nodes_and_edges(commits, collaborators, repository_id)
        logger.info('All nodes and edges added')
        return collaborators
