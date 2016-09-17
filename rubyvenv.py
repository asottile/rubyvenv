from __future__ import absolute_import
from __future__ import unicode_literals

import argparse
import collections
import gzip
import io
import os.path
import platform

import distro
import six


RVM = 'https://rvm.io/binaries/{name}/{version}/{arch}/'


Platform = collections.namedtuple('Platform', ('name', 'version', 'arch'))
Version = collections.namedtuple('Version', ('version', 'url'))


def cache_dir():
    return os.path.join(
        os.getenv('XDG_CACHE_HOME', os.path.expanduser('~/.cache')),
        'rubyvenv',
    )


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


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('dest', nargs='?', metavar='DEST_DIR')
    parser.add_argument(
        '--list-versions', action='store_true',
        help='List versions available for your system',
    )
    args = parser.parse_args(argv)

    if args.list_versions:
        return list_versions()
    else:
        raise NotImplementedError


if __name__ == '__main__':
    exit(main())
