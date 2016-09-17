from __future__ import absolute_import
from __future__ import unicode_literals

import io
import os
import platform

import distro
import mock
import pytest
import six

import rubyvenv
from testing.resources import resource


def test_cache_dir_xdg_variable():
    with mock.patch.dict(os.environ, {'XDG_CACHE_HOME': '/foo'}):
        assert rubyvenv.cache_dir() == '/foo/rubyvenv'


def test_mkdirp(tmpdir):
    path = tmpdir.join('foo/bar')
    assert not path.exists()
    rubyvenv.mkdirp(path.strpath)
    assert path.isdir()
    rubyvenv.mkdirp(path.strpath)


def test_gets_a_hrefs_trivial():
    parser = rubyvenv.GetsAHrefs()
    parser.feed('')
    assert parser.hrefs == []


def test_gets_a_hrefs_ubuntu_16_04_x86_64():
    contents = io.open(resource('ubuntu_16_04_x86_64.htm')).read()
    parser = rubyvenv.GetsAHrefs()
    parser.feed(contents)
    assert parser.hrefs == [
        '../',
        'ruby-2.0.0-p648.tar.bz2',
        'ruby-2.1.5.tar.bz2',
        'ruby-2.1.9.tar.bz2',
        'ruby-2.2.5.tar.bz2',
        'ruby-2.3.0.tar.bz2',
        'ruby-2.3.1.tar.bz2',
    ]


def test_decode_response_non_gzip():
    assert rubyvenv._decode_response(b'foo') == 'foo'


def test_decode_response_gzip():
    contents = io.open(resource('ubuntu_16_04_x86_64.htm.gzip'), 'rb').read()
    ret = rubyvenv._decode_response(contents)
    assert 'ruby-2.0.0-p648.tar.bz2' in ret


@pytest.mark.parametrize(
    ('filename', 'expected'),
    (
        ('ruby-2.0.0-p648.tar.bz2', '2.0.0-p648'),
        ('ruby-2.3.1.tar.bz2', '2.3.1'),
    ),
)
def test_filename_to_version(filename, expected):
    assert rubyvenv._filename_to_version(filename) == expected


@pytest.yield_fixture
def returns_xenial():
    contents = io.open(resource('ubuntu_16_04_x86_64.htm.gzip'), 'rb').read()
    with mock.patch.object(
        six.moves.urllib.request, 'urlopen',
        **{'return_value.read.return_value': contents}
    ):
        yield


@pytest.mark.usefixtures('returns_xenial')
def test_get_prebuilt_versions():
    plat = rubyvenv.Platform('ubuntu', '16.04', 'x86_64')
    ret = rubyvenv.get_prebuilt_versions(plat)
    assert ret == (
        rubyvenv.Version(
            '2.0.0-p648',
            'https://rvm.io/binaries/ubuntu/16.04/x86_64/'
            'ruby-2.0.0-p648.tar.bz2',
        ),
        rubyvenv.Version(
            '2.1.5',
            'https://rvm.io/binaries/ubuntu/16.04/x86_64/ruby-2.1.5.tar.bz2',
        ),
        rubyvenv.Version(
            '2.1.9',
            'https://rvm.io/binaries/ubuntu/16.04/x86_64/ruby-2.1.9.tar.bz2',
        ),
        rubyvenv.Version(
            '2.2.5',
            'https://rvm.io/binaries/ubuntu/16.04/x86_64/ruby-2.2.5.tar.bz2',
        ),
        rubyvenv.Version(
            '2.3.0',
            'https://rvm.io/binaries/ubuntu/16.04/x86_64/ruby-2.3.0.tar.bz2',
        ),
        rubyvenv.Version(
            '2.3.1',
            'https://rvm.io/binaries/ubuntu/16.04/x86_64/ruby-2.3.1.tar.bz2',
        ),
    )


@pytest.yield_fixture
def xenial():
    with mock.patch.object(platform, 'machine', return_value='x86_64'):
        with mock.patch.object(distro, 'id', return_value='ubuntu'):
            with mock.patch.object(distro, 'version', return_value='16.04'):
                yield


@pytest.mark.usefixtures('xenial', 'returns_xenial')
def test_list_versions(capsys):
    ret = rubyvenv.main(('--list',))
    assert ret is None
    out, _ = capsys.readouterr()
    assert out == (
        'Available versions for ubuntu 16.04 (x86_64):\n'
        '\n'
        'Prebuilt:\n'
        '    - 2.0.0-p648\n'
        '    - 2.1.5\n'
        '    - 2.1.9\n'
        '    - 2.2.5\n'
        '    - 2.3.0\n'
        '    - 2.3.1\n'
    )
