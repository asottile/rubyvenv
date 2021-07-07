import argparse
import functools
import gzip
import html.parser
import io
import os.path
import pipes
import platform
import shutil
import tarfile
import tempfile
import urllib.parse
import urllib.request
from typing import Callable
from typing import ContextManager
from typing import IO
from typing import List
from typing import NamedTuple
from typing import Optional
from typing import Sequence
from typing import Tuple

import distro

# Roughly stolen from python virtualenv 15.0.1
ACTIVATE = '''\
# This file must be used with "source bin/activate" *from bash*
# you cannot run it directly

deactivate_rubyvenv () {
    # reset old environment variables
    # ! [ -z ${VAR+_} ] returns true if VAR is declared at all
    if ! [ -z "${_OLD_RUBYVENV_PATH+_}" ] ; then
        PATH="$_OLD_RUBYVENV_PATH"
        export PATH
        unset _OLD_RUBYVENV_PATH
    fi

    # This should detect bash and zsh, which have a hash command that must
    # be called to get it to forget past commands.  Without forgetting
    # past commands the $PATH changes we made may not be respected
    if [ -n "${BASH-}" ] || [ -n "${ZSH_VERSION-}" ] ; then
        hash -r 2>/dev/null
    fi

    if ! [ -z "${_OLD_RUBYVENV_PS1+_}" ] ; then
        PS1="$_OLD_RUBYVENV_PS1"
        export PS1
        unset _OLD_RUBYVENV_PS1
    fi

    if ! [ -z "${_OLD_RUBYVENV_GEM_HOME+_}" ] ; then
        GEM_HOME="$_OLD_RUBYVENV_GEM_HOME"
        export GEM_HOME
        unset _OLD_RUBYVENV_GEM_HOME
    fi

    unset RUBYVENV
    if [ ! "${1-}" = "nondestructive" ] ; then
        # Self destruct!
        unset -f deactivate_rubyvenv
    fi
}

# unset irrelevant variables
deactivate_rubyvenv nondestructive

RUBYVENV=DIRECTORY
export RUBYVENV

_OLD_RUBYVENV_PATH="$PATH"
PATH="${RUBYVENV}/bin:${RUBYVENV}/lib/gems/bin:${PATH}"
export PATH

# This should detect bash and zsh, which have a hash command that must
# be called to get it to forget past commands.  Without forgetting
# past commands the $PATH changes we made may not be respected
if [ -n "${BASH-}" ] || [ -n "${ZSH_VERSION-}" ] ; then
    hash -r 2>/dev/null
fi

_OLD_RUBYVENV_PS1="$PS1"
PS1="($(basename "$RUBYVENV")) $PS1"
export PS1
'''

SET_GEM_HOME = '''\
_OLD_RUBYVENV_GEM_HOME="${GEM_HOME:-}"
GEM_HOME="$RUBYVENV/lib/gems"
export GEM_HOME
'''


class Platform(NamedTuple):
    name: str
    version: str
    arch: str

    @property
    def rvm_url(self) -> str:
        return (
            f'https://rvm.io/binaries/{self.name}/{self.version}/{self.arch}/'
        )


class Version(NamedTuple):
    version: str
    url: str


def get_cache_dir() -> str:
    return os.path.join(
        os.getenv('XDG_CACHE_HOME', os.path.expanduser('~/.cache')),
        'rubyvenv',
    )


def ensure_cache_file(
        relpath: str,
        get_fileobj: Callable[[], ContextManager[IO[bytes]]],
) -> str:
    cache_dir = get_cache_dir()
    path = os.path.join(cache_dir, relpath)
    if os.path.exists(path):
        return path
    else:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # Write to a temporary file and then rename for atomicity
        tmpdir = os.path.join(cache_dir, 'tmp')
        os.makedirs(tmpdir, exist_ok=True)
        try:
            with tempfile.NamedTemporaryFile(dir=tmpdir, delete=False) as dst:
                with get_fileobj() as src:
                    shutil.copyfileobj(src, dst)
        except BaseException:
            os.remove(dst.name)
            raise
        os.rename(dst.name, path)
        return path


def get_platform_info() -> Platform:
    return Platform(distro.id(), distro.version(), platform.machine())


class GetsAHrefs(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: List[Optional[str]] = []

    def handle_starttag(
            self,
            tag: str,
            attrs: List[Tuple[str, Optional[str]]],
    ) -> None:
        if tag == 'a':
            self.hrefs.append(dict(attrs)['href'])


def _decode_response(resp_bytes: bytes) -> str:
    """Even though we request identity, rvm.io sends us gzip."""
    try:
        # Try UTF-8 first, in case they ever fix their bug
        return resp_bytes.decode('UTF-8')
    except UnicodeDecodeError:
        with io.BytesIO(resp_bytes) as bytesio:
            with gzip.GzipFile(fileobj=bytesio) as gzipfile:
                return gzipfile.read().decode('UTF-8')


def _filename_to_version(filename: str) -> str:
    assert filename.endswith('.tar.bz2')
    assert filename.startswith('ruby-')
    return filename[len('ruby-'):-1 * len('.tar.bz2')]


def _version_to_filename(version: str) -> str:
    return f'ruby-{version}.tar.bz2'


def _download_url(platform_info: Platform, version: str) -> str:
    return urllib.parse.urljoin(
        platform_info.rvm_url, _version_to_filename(version),
    )


def get_prebuilt_versions(platform_info: Platform) -> Tuple[Version, ...]:
    url = platform_info.rvm_url
    resp = _decode_response(urllib.request.urlopen(url).read())
    parser = GetsAHrefs()
    parser.feed(resp)
    return tuple(
        Version(
            _filename_to_version(href),
            urllib.parse.urljoin(url, href),
        )
        for href in parser.hrefs
        if href is not None and href.startswith('ruby-')
    )


def list_versions() -> int:
    platform_info = get_platform_info()
    prebuilt_versions = get_prebuilt_versions(platform_info)
    print(
        'Available versions for {name} {version} ({arch}):\n'.format(
            **platform_info._asdict(),
        ),
    )
    print('Prebuilt:')
    for version in prebuilt_versions:
        print(f'    - {version.version}')
    return 0


def pick_version(version: str) -> Version:
    platform_info = get_platform_info()
    if version == 'latest':
        return get_prebuilt_versions(platform_info)[-1]
    else:
        return Version(version, _download_url(platform_info, version))


def _write_activate(dest: str, more: str = '') -> None:
    with open(os.path.join(dest, 'bin', 'activate'), 'w') as activate:
        activate.write(ACTIVATE.replace('DIRECTORY', pipes.quote(dest)))
        activate.write(more)


def make_environment(dest: str, version: Version) -> int:
    platform_info = get_platform_info()
    filename = _version_to_filename(version.version)
    cache_file = '{name}/{version}/{arch}/{filename}'.format(
        filename=filename, **platform_info._asdict(),
    )
    get_fileobj = functools.partial(urllib.request.urlopen, version.url)
    tar_filename = ensure_cache_file(cache_file, get_fileobj)
    dest = os.path.abspath(dest)
    os.makedirs(dest, exist_ok=True)
    with tarfile.open(tar_filename) as tar_file:
        # Remove the /cache directory.
        # It is unnecessary, and on precise it is a broken symlink
        members = [
            member for member in tar_file.getmembers()
            if not member.name.endswith('/cache')
            if '/cache/' not in member.name
        ]

        # Remove the first path segment so we extract directly into the
        # destination directory
        for member in members:
            if os.sep in member.name:
                _, member.name = member.name.split(os.sep, 1)
            else:
                member.name = ''
        tar_file.extractall(dest, members)
    _write_activate(dest)
    return 0


def make_system_environment(dest: str) -> int:
    os.makedirs(os.path.join(dest, 'bin'), exist_ok=True)
    ruby = shutil.which('ruby')
    gem = shutil.which('gem')
    assert ruby and gem, (ruby, gem)
    _write_activate(dest, more=SET_GEM_HOME)
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('dest', nargs='?', metavar='DEST_DIR')
    parser.add_argument('--ruby', default='latest')
    parser.add_argument(
        '--list-versions', action='store_true',
        help='List versions available for your system',
    )
    args = parser.parse_args(argv)

    if args.list_versions:
        return list_versions()
    else:
        if not args.dest:
            parser.error('DEST_DIR is required')
        args.dest = os.path.abspath(args.dest)
        if args.ruby == 'system':
            return make_system_environment(args.dest)
        else:
            version = pick_version(args.ruby)
            return make_environment(args.dest, version)


if __name__ == '__main__':
    exit(main())
