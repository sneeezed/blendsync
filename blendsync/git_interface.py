import json
import os
import subprocess


class GitError(Exception):
    pass


# Cached once at module load — git availability doesn't change during a session.
# If the user installs git while Blender is open they must restart Blender.
_git_available = None


def is_available():
    global _git_available
    if _git_available is None:
        try:
            subprocess.run(['git', '--version'], capture_output=True, check=True)
            _git_available = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            _git_available = False
    return _git_available


# Cached per-path — .git presence doesn't change unless the user runs init_repo()
# or manually deletes the .git folder while Blender is open (unsupported).
_repo_cache: dict = {}


def is_repo(path):
    if path not in _repo_cache:
        _repo_cache[path] = os.path.isdir(os.path.join(path, '.git'))
    return _repo_cache[path]


def _invalidate_repo_cache(path=None):
    """Call after creating or destroying a repo so is_repo() picks up the change."""
    if path is None:
        _repo_cache.clear()
    else:
        _repo_cache.pop(path, None)


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
    # Try git >= 2.28 (-b flag); fall back to symbolic-ref for older git
    try:
        run_git(['init', '-b', 'main'], cwd=path)
    except GitError:
        run_git(['init'], cwd=path)
        try:
            run_git(['symbolic-ref', 'HEAD', 'refs/heads/main'], cwd=path)
        except GitError:
            pass

    try:
        run_git(['config', 'user.email', 'blendsync@local'], cwd=path)
        run_git(['config', 'user.name', 'BlendSync'], cwd=path)
    except GitError:
        pass

    gitignore = os.path.join(path, '.gitignore')
    if not os.path.exists(gitignore):
        with open(gitignore, 'w') as f:
            f.write('*.blend1\n*.blend2\n')

    # Initial commit so 'main' branch actually exists
    run_git(['add', '.'], cwd=path)
    try:
        run_git(['commit', '-m', 'Initialize BlendSync repository'], cwd=path)
    except GitError:
        pass  # Nothing to commit is fine

    # Bust the cache so is_repo() immediately returns True for this path
    _invalidate_repo_cache(path)


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

def _parse_refs(refs_str):
    """Parse git %D decoration into a list of local branch names."""
    if not refs_str.strip():
        return []
    branches = []
    for ref in refs_str.split(','):
        ref = ref.strip()
        if ref.startswith('HEAD -> '):
            branches.append(ref[8:])
        elif ref.startswith('HEAD') or '/' in ref or ref.startswith('tag:'):
            pass  # skip detached HEAD, remote refs, tags
        else:
            branches.append(ref)
    return branches


def get_log(repo_path, count=50):
    """Return list of dicts: hash, message, date, refs (local branch names)."""
    try:
        output = run_git(
            ['log', f'--max-count={count}',
             '--pretty=format:%h|||%s|||%ad|||%D', '--date=short'],
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
                'refs': _parse_refs(parts[3]) if len(parts) > 3 else [],
            })
        return entries
    except GitError:
        return []


def get_snapshot_at_commit(repo_path, commit_ref, json_path):
    """Load the JSON snapshot stored at a given commit.
    json_path may be absolute or relative to repo_path."""
    if os.path.isabs(json_path):
        json_path = os.path.relpath(json_path, repo_path)
    # Normalize to forward slashes (git show requires this even on Windows)
    json_path = json_path.replace('\\', '/')
    output = run_git(['show', f'{commit_ref}:{json_path}'], cwd=repo_path)
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


def get_head_hash(repo_path):
    """Return the short hash of the current HEAD commit."""
    try:
        return run_git(['rev-parse', '--short', 'HEAD'], cwd=repo_path)
    except GitError:
        return None


def get_effective_commit(repo_path):
    """Return the hash that the working tree is currently at.
    If the user reverted to an older commit, reads .blendsync_head.
    Otherwise returns git HEAD."""
    import os
    marker = os.path.join(repo_path, '.blendsync_head')
    if os.path.exists(marker):
        try:
            with open(marker) as f:
                h = f.read().strip()
            if h:
                return h
        except OSError:
            pass
    return get_head_hash(repo_path)


def write_head_marker(repo_path, commit_hash):
    import os
    marker = os.path.join(repo_path, '.blendsync_head')
    with open(marker, 'w') as f:
        f.write(commit_hash)


def clear_head_marker(repo_path):
    import os
    marker = os.path.join(repo_path, '.blendsync_head')
    if os.path.exists(marker):
        os.remove(marker)


def create_branch(repo_path, name):
    run_git(['checkout', '-b', name], cwd=repo_path)


def checkout_branch(repo_path, name):
    run_git(['checkout', name], cwd=repo_path)


# ── Revert ─────────────────────────────────────────────────────────────────

def revert_to_commit(repo_path, commit_hash):
    """Restore working tree to the state at commit_hash without moving HEAD."""
    run_git(['checkout', commit_hash, '--', '.'], cwd=repo_path)
