"""Assemble Pages from trusted main and immutable PR blobs; never run PR code.

Python standard library + Git only. Authentication uses the runner's temporary,
read-only GITHUB_TOKEN (passed as GH_TOKEN), never a repository secret.
"""
import argparse
import base64
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile
import urllib.request


class UnsafeTree(ValueError):
    """A source cannot be safely published as a standalone static directory."""


def git(source, *args, env=None):
    return subprocess.check_output(
        ['git', '-C', str(source), *args], env=env, stderr=subprocess.PIPE
    )


def materialize(source, sha, destination, production=False):
    """Copy tracked regular files byte-for-byte, ignoring only .github metadata.

    Reading blobs avoids checkout hooks, submodules, LFS/smudge filters, and
    .gitattributes export-ignore/export-subst rewriting the app or its assets.
    Validate the entire tree before writing; links must never escape a preview.
    """
    if not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise UnsafeTree('Expected an immutable commit SHA')
    entries = []
    for record in git(source, 'ls-tree', '-rz', '--full-tree', sha).split(b'\0'):
        if not record:
            continue
        metadata, raw_path = record.split(b'\t', 1)
        mode, kind, blob = metadata.decode('ascii').split()
        name = raw_path.decode('utf-8')
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or '.git' in path.parts:
            raise UnsafeTree('Unsafe tracked path')
        if production and path.parts[0] == 'previews':
            raise UnsafeTree('Production uses the reserved previews/ directory')
        if path.parts[0] == '.github':
            continue
        if mode not in ('100644', '100755') or kind != 'blob':
            raise UnsafeTree('Symlinks and submodules are not supported')
        entries.append((name, blob))
    if not any(name == 'index.html' for name, _ in entries):
        raise UnsafeTree('Missing root index.html')
    destination.mkdir(parents=True, exist_ok=False)
    for name, blob in entries:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(git(source, 'cat-file', 'blob', blob))


def open_pulls(repository, token):
    """Paginate rather than silently dropping previews after the first 30 PRs."""
    pulls = []
    page = 1
    while True:
        url = (f'https://api.github.com/repos/{repository}/pulls'
               f'?state=open&base=main&per_page=100&page={page}')
        request = urllib.request.Request(url, headers={
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
        })
        with urllib.request.urlopen(request, timeout=60) as response:
            batch = json.load(response)
        pulls.extend(batch)
        if len(batch) < 100:
            return pulls
        page += 1


def eligible_pulls(pulls, repository):
    # PR directories share the production browser origin (including localStorage).
    # Do not automatically publish arbitrary fork JavaScript on that origin.
    eligible = []
    for pr in pulls:
        if pr['state'] != 'open' or pr['base']['ref'] != 'main':
            continue
        head_repo = pr['head'].get('repo') or {}
        if head_repo.get('full_name') != repository:
            continue
        number, sha = pr['number'], pr['head']['sha']
        if type(number) is not int or number <= 0 or not re.fullmatch(r'[0-9a-f]{40}', sha):
            raise ValueError('Invalid PR identity from GitHub')
        eligible.append((number, sha))
    return sorted(eligible)


def fetch_commit(source, repository, sha, token):
    # Read-only credentials exist only in this subprocess's environment, not in
    # .git/config, the command line, the published files, or workflow output.
    auth = base64.b64encode(f'x-access-token:{token}'.encode()).decode()
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GIT_CONFIG_COUNT='1',
               GIT_CONFIG_KEY_0='http.https://github.com/.extraheader',
               GIT_CONFIG_VALUE_0=f'AUTHORIZATION: basic {auth}')
    git(source, '-c', 'core.hooksPath=/dev/null', 'fetch', '--quiet', '--no-tags',
        '--no-recurse-submodules', '--depth=1',
        f'https://github.com/{repository}.git', sha, env=env)


def assemble(source, production_sha, pulls, output, fetch):
    """Rebuild the whole artifact; closed PRs disappear without a cleanup branch."""
    if output.exists():
        raise ValueError('Output must be a new directory')
    published, skipped = [], []
    # A failed API/fetch/production copy aborts before deployment, leaving the
    # previously published site intact. Never silently deploy a partial fetch.
    with tempfile.TemporaryDirectory() as temp:
        site = Path(temp) / 'site'
        materialize(source, production_sha, site, production=True)
        for number, sha in pulls:
            fetch(sha)
            preview = site / 'previews' / f'pr-{number}'
            try:
                materialize(source, sha, preview)
            except UnsafeTree as error:
                skipped.append((number, str(error)))
                continue
            published.append((number, sha))
        # GitHub Actions deploys raw static files; no Jekyll or PR build step.
        if not (site / '.nojekyll').exists():
            (site / '.nojekyll').touch()
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(site), str(output))
    return published, skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path.cwd())
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repository = os.environ['GITHUB_REPOSITORY']
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('Invalid repository name')
    token = os.environ['GH_TOKEN']
    production_sha = git(args.source, 'rev-parse', 'HEAD').decode().strip()
    pulls = eligible_pulls(open_pulls(repository, token), repository)
    published, skipped = assemble(
        args.source, production_sha, pulls, args.output,
        lambda sha: fetch_commit(args.source, repository, sha, token),
    )
    owner, name = repository.split('/')
    base = f'https://{owner}.github.io/{name}/'
    summary = [f'Production: {base} (`{production_sha}`)', '',
               'Previews use exact PR head files; fork PRs are not published.', '']
    summary += [f'- PR #{number}: {base}previews/pr-{number}/ (`{sha}`)'
                for number, sha in published]
    summary += [f'- PR #{number}: skipped — {reason}' for number, reason in skipped]
    if not published:
        summary.append('No eligible open PR previews.')
    report = '\n'.join(summary) + '\n'
    print(report)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as handle:
            handle.write(report)


if __name__ == '__main__':
    main()
