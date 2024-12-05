import subprocess

class CommandRunner:
    def __init__(self, repo_dir):
        self.repo_dir = repo_dir

    def run_command(self, command):
        """Runs a git command in the specified repository directory.

        Args:
            command (list): The git command to run as a list of arguments.

        Returns:
            tuple: A tuple containing the command's stdout as the first element
            and an error message as the second element. If the command succeeds,
            the error message will be None. If the command fails, stdout will be None.
        """
        result = subprocess.run(['git', '-C', self.repo_dir] + command, capture_output=True, text=True)
        if result.returncode != 0:
            return None, result.stderr.strip()
        return result.stdout.strip(), None

# # Example usage
# repo_directory = '/path/to/repo'
# command_runner = CommandRunner(repo_directory)
# stdout, stderr = command_runner.run_command(['status'])
# if stderr:
#     print(f"Error: {stderr}")
# else:
#     print(stdout)
