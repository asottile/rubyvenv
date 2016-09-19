from __future__ import absolute_import
from __future__ import unicode_literals

import argparse
import collections
import contextlib
import functools
import gzip
import io
import os.path
import pipes
import platform
import shutil
import tarfile
import tempfile

import distro
import six


RVM = 'https://rvm.io/binaries/{name}/{version}/{arch}/'


Platform = collections.namedtuple('Platform', ('name', 'version', 'arch'))
Version = collections.namedtuple('Version', ('version', 'url'))


def get_cache_dir():
    return os.path.join(
        os.getenv('XDG_CACHE_HOME', os.path.expanduser('~/.cache')),
        'rubyvenv',
    )


def ensure_cache_file(relpath, get_fileobj):
    cache_dir = get_cache_dir()
    path = os.path.join(cache_dir, relpath)
    if os.path.exists(path):
        return path
    else:
        mkdirp(os.path.dirname(path))
        # Write to a temporary file and then rename for atomicity
        tmpdir = os.path.join(cache_dir, 'tmp')
        mkdirp(tmpdir)
        try:
            with tempfile.NamedTemporaryFile(dir=tmpdir, delete=False) as dst:
                with get_fileobj() as src:
                    shutil.copyfileobj(src, dst)
        except BaseException:
            os.remove(dst.name)
            raise
        os.rename(dst.name, path)
        return path


def mkdirp(path):
    try:
        os.makedirs(path)
    except OSError:
        if not os.path.isdir(path):
            raise


def get_platform_info():
    return Platform(distro.id(), distro.version(), platform.machine())


class GetsAHrefs(six.moves.html_parser.HTMLParser):
    def __init__(self):
        # Old style class in python2
        six.moves.html_parser.HTMLParser.__init__(self)
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.hrefs.append(dict(attrs)['href'])


def _decode_response(resp_bytes):
    """Even though we request identity, rvm.io sends us gzip."""
    try:
        # Try UTF-8 first, in case they ever fix their bug
        return resp_bytes.decode('UTF-8')
    except UnicodeDecodeError:
        with io.BytesIO(resp_bytes) as bytesio:
            with gzip.GzipFile(fileobj=bytesio) as gzipfile:
                return gzipfile.read().decode('UTF-8')


def _filename_to_version(filename):
    assert filename.endswith('.tar.bz2')
    assert filename.startswith('ruby-')
    return filename[len('ruby-'):-1 * len('.tar.bz2')]


def _version_to_filename(version):
    return 'ruby-{}.tar.bz2'.format(version)


def _download_url(platform_info, version):
    return six.moves.urllib_parse.urljoin(
        RVM.format(**platform_info._asdict()), _version_to_filename(version),
    )


def get_prebuilt_versions(platform_info):
    url = RVM.format(**platform_info._asdict())
    resp = _decode_response(six.moves.urllib.request.urlopen(url).read())
    parser = GetsAHrefs()
    parser.feed(resp)
    return tuple(
        Version(
            _filename_to_version(href),
            six.moves.urllib_parse.urljoin(url, href),
        )
        for href in parser.hrefs
        if href.startswith('ruby-')
    )


def list_versions():
    platform_info = get_platform_info()
    prebuilt_versions = get_prebuilt_versions(platform_info)
    print('Available versions for {name} {version} ({arch}):\n'.format(
        **platform_info._asdict()
    ))
    print('Prebuilt:')
    for version in prebuilt_versions:
        print('    - {}'.format(version.version))


def pick_version(version):
    platform_info = get_platform_info()
    if version != 'latest':
        return Version(version, _download_url(platform_info, version))
    else:
        return get_prebuilt_versions(platform_info)[-1]


def urlopen_closable(*args):
    return contextlib.closing(six.moves.urllib.request.urlopen(*args))


def make_environment(dest, version):
    platform_info = get_platform_info()
    filename = _version_to_filename(version.version)
    cache_file = '{name}/{version}/{arch}/{filename}'.format(
        filename=filename, **platform_info._asdict()
    )
    get_fileobj = functools.partial(urlopen_closable, version.url)
    tar_filename = ensure_cache_file(cache_file, get_fileobj)
    dest = os.path.abspath(dest)
    mkdirp(dest)
    with tarfile.open(tar_filename) as tar_file:
        # Remove the /cache directory.
        # It is unnecessary, and on precise it is a broken symlink
        members = [
            member for member in tar_file.getmembers()
            if (
                not member.name.endswith('/cache') and
                '/cache/' not in member.name
            )
        ]

        # Remove the first path segment so we extract directly into the
        # destination directory
        for member in members:
            if os.sep in member.name:
                _, member.name = member.name.split(os.sep, 1)
            else:
                member.name = ''
        tar_file.extractall(dest, members)
    with io.open(os.path.join(dest, 'bin', 'activate'), 'w') as activate:
        activate.write(ACTIVATE.replace('DIRECTORY', pipes.quote(dest)))


def main(argv=None):
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
        version = pick_version(args.ruby)
        return make_environment(args.dest, version)


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
PATH="$RUBYVENV/bin:$PATH"
export PATH

_OLD_RUBYVENV_PS1="$PS1"
PS1="($(basename "$RUBYVENV")) $PS1"
export PS1

# This should detect bash and zsh, which have a hash command that must
# be called to get it to forget past commands.  Without forgetting
# past commands the $PATH changes we made may not be respected
if [ -n "${BASH-}" ] || [ -n "${ZSH_VERSION-}" ] ; then
    hash -r 2>/dev/null
fi
'''

if __name__ == '__main__':
    exit(main())
