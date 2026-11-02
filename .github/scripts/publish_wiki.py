"""Publish only the maintained whitepaper and an additive Home link.

Uses the repository-scoped GitHub Actions token. It never initialises a Wiki,
changes visibility, executes Wiki content or overwrites an unmanaged paper.
"""
import base64
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

MARKER = '<!-- atlas-whitepaper:managed:v1 -->'
START = '<!-- atlas-whitepaper:index:start -->'
END = '<!-- atlas-whitepaper:index:end -->'


def merge_pages(source, destination):
    paper = source / 'Whitepaper.md'
    fragment = source / 'Home.md'
    for item in (paper, fragment):
        if item.is_symlink() or not item.is_file() or item.stat().st_size > 200_000:
            raise ValueError('Expected bounded regular Wiki source files')
    content = paper.read_text(encoding='utf-8')
    if MARKER not in content:
        raise ValueError('Whitepaper source lacks ownership marker')
    target = destination / 'Whitepaper.md'
    if target.is_symlink():
        raise ValueError('Refusing a symbolic-link Wiki target')
    if target.exists() and MARKER not in target.read_text(encoding='utf-8'):
        raise ValueError('Existing Whitepaper is unmanaged; review before replacing it')
    home = destination / 'Home.md'
    if home.is_symlink():
        raise ValueError('Refusing a symbolic-link Wiki Home')
    original = home.read_text(encoding='utf-8') if home.exists() else '# Project Wiki\n'
    block = START + '\n' + fragment.read_text(encoding='utf-8').strip() + '\n' + END
    if START in original or END in original:
        if original.count(START) != 1 or original.count(END) != 1 or original.index(START) > original.index(END):
            raise ValueError('Ambiguous managed index markers')
        result = original[:original.index(START)] + block + original[original.index(END) + len(END):]
    else:
        result = original.rstrip() + '\n\n' + block + '\n'
    target.write_text(content, encoding='utf-8')
    home.write_text(result, encoding='utf-8')


def receipt(status, repository, **details):
    data = {'status': status, 'repository': repository,
            'source_commit': os.environ.get('GITHUB_SHA'), **details}
    print(json.dumps(data, sort_keys=True))
    Path('wiki-publication.json').write_text(json.dumps(data, indent=2) + '\n')
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as stream:
            stream.write(f'## Wiki publication: {status}\n\n')
            if status == 'BLOCKED_UNINITIALISED':
                stream.write(f'The paper is committed under `wiki/Whitepaper.md`, but is **not published to the Wiki**. Create the first page at https://github.com/{repository}/wiki/_new . The `gollum` event will retry publication.\n')
            else:
                stream.write(f'https://github.com/{repository}/wiki/Whitepaper\n\n{json.dumps(details)}\n')


def main():
    repository = os.environ.get('GITHUB_REPOSITORY', '')
    if not re.fullmatch(r'Albertito-AI/[A-Za-z0-9_.-]+', repository):
        raise ValueError('Expected an explicitly identified owner repository')
    token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    if not token:
        raise ValueError('An authorised GitHub token is required; none is discovered automatically')
    source = Path(__file__).resolve().parents[2] / 'wiki'
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GIT_CONFIG_COUNT='1',
               GIT_CONFIG_KEY_0='http.https://github.com/.extraheader',
               GIT_CONFIG_VALUE_0='AUTHORIZATION: basic ' + base64.b64encode(('x-access-token:' + token).encode()).decode())
    url = f'https://github.com/{repository}.wiki.git'

    def git(args, cwd=None, check=True):
        r = subprocess.run(['git', *args], cwd=cwd, env=env, text=True,
                           capture_output=True, timeout=90)
        if check and r.returncode:
            raise RuntimeError(r.stderr.strip() or 'Git operation failed')
        return r

    available = git(['ls-remote', url, 'HEAD'], check=False)
    if available.returncode:
        if 'not found' in available.stderr.lower():
            receipt('BLOCKED_UNINITIALISED', repository)
            return
        raise RuntimeError(available.stderr.strip())
    if not available.stdout.strip():
        receipt('BLOCKED_UNINITIALISED', repository)
        return
    with tempfile.TemporaryDirectory(prefix='wiki-publication-') as temporary:
        destination = Path(temporary) / 'wiki'
        git(['clone', '--depth', '1', url, str(destination)])
        merge_pages(source, destination)
        git(['add', '--', 'Whitepaper.md', 'Home.md'], destination)
        changed = git(['diff', '--cached', '--quiet'], destination, check=False)
        if changed.returncode not in (0, 1):
            raise RuntimeError('Could not inspect Wiki changes')
        if changed.returncode == 0:
            receipt('ALREADY_CURRENT', repository, wiki_commit=git(['rev-parse', 'HEAD'], destination).stdout.strip())
            return
        git(['-c', 'user.name=github-actions[bot]', '-c', 'user.email=41898282+github-actions[bot]@users.noreply.github.com',
             'commit', '-m', 'Publish project foundations and future-direction whitepaper'], destination)
        # A concurrent Wiki edit makes this ordinary non-forced push fail safely.
        git(['push', 'origin', 'HEAD'], destination)
        expected = git(['rev-parse', 'HEAD'], destination).stdout.strip()
        actual = git(['ls-remote', url, 'HEAD']).stdout.split()[0]
        if actual != expected:
            raise RuntimeError('Wiki head changed; reconcile before claiming publication')
        receipt('PUBLISHED', repository, wiki_commit=expected)


if __name__ == '__main__':
    main()
