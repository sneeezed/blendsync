import json
import os
import subprocess


class GitError(Exception):
    pass


def is_available():
    try:
        subprocess.run(['git', '--version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def is_repo(path):
    return os.path.isdir(os.path.join(path, '.git'))


def run_git(args, cwd):
    result = subprocess.run(
        ['git'] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise GitError(result.stderr.strip())
    return result.stdout.strip()


def init_repo(path):
    run_git(['init'], cwd=path)
    # Set a default identity so commits work without global git config
    try:
        run_git(['config', 'user.email', 'blendsync@local'], cwd=path)
        run_git(['config', 'user.name', 'BlendSync'], cwd=path)
    except GitError:
        pass
    gitignore = os.path.join(path, '.gitignore')
    if not os.path.exists(gitignore):
        with open(gitignore, 'w') as f:
            f.write('*.blend1\n*.blend2\n')


def commit(repo_path, message):
    run_git(['add', '.'], cwd=repo_path)
    run_git(['commit', '-m', message], cwd=repo_path)


def has_changes(repo_path):
    try:
        output = run_git(['status', '--porcelain'], cwd=repo_path)
        return bool(output.strip())
    except GitError:
        return False


# ── Log ────────────────────────────────────────────────────────────────────

def get_log(repo_path, count=50):
    """Return a list of dicts: hash, message, date."""
    try:
        output = run_git(
            ['log', f'--max-count={count}',
             '--pretty=format:%h|||%s|||%ad', '--date=short'],
            cwd=repo_path,
        )
        if not output:
            return []
        entries = []
        for line in output.split('\n'):
            if '|||' not in line:
                continue
            parts = line.split('|||')
            entries.append({
                'hash': parts[0].strip(),
                'message': parts[1].strip() if len(parts) > 1 else '',
                'date': parts[2].strip() if len(parts) > 2 else '',
            })
        return entries
    except GitError:
        return []


def get_snapshot_at_commit(repo_path, commit_hash, json_filename):
    """Return the parsed JSON snapshot stored at a specific commit."""
    output = run_git(['show', f'{commit_hash}:{json_filename}'], cwd=repo_path)
    return json.loads(output)


# ── Branches ───────────────────────────────────────────────────────────────

def get_branches(repo_path):
    """Return (current_branch_name, [{'name': str, 'is_current': bool}])."""
    try:
        output = run_git(
            ['branch', '--format=%(refname:short)|||%(HEAD)'],
            cwd=repo_path,
        )
        branches = []
        current = None
        for line in output.split('\n'):
            if '|||' not in line:
                continue
            name, head = line.split('|||', 1)
            name = name.strip()
            is_current = head.strip() == '*'
            branches.append({'name': name, 'is_current': is_current})
            if is_current:
                current = name
        return current, branches
    except GitError:
        return None, []


def get_current_branch(repo_path):
    try:
        return run_git(['rev-parse', '--abbrev-ref', 'HEAD'], cwd=repo_path)
    except GitError:
        return None


def create_branch(repo_path, name):
    """Create and immediately switch to a new branch."""
    run_git(['checkout', '-b', name], cwd=repo_path)


def checkout_branch(repo_path, name):
    """Switch to an existing branch."""
    run_git(['checkout', name], cwd=repo_path)


# ── Revert ─────────────────────────────────────────────────────────────────

def revert_to_commit(repo_path, commit_hash):
    """Restore the working tree to the state at commit_hash without moving HEAD."""
    run_git(['checkout', commit_hash, '--', '.'], cwd=repo_path)
