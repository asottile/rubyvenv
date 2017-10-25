from __future__ import absolute_import
from __future__ import unicode_literals

import io
import os
import platform
import subprocess

import distro
import mock
import pytest
import six

import rubyvenv
from testing.resources import resource


@pytest.yield_fixture
def mocked_cache(tmpdir):
    cache_dir = tmpdir.join('.cache')
    with mock.patch.dict(os.environ, {'XDG_CACHE_HOME': cache_dir.strpath}):
        yield cache_dir.join('rubyvenv')


def test_get_cache_dir_xdg_variable():
    with mock.patch.dict(os.environ, {'XDG_CACHE_HOME': '/foo'}):
        assert rubyvenv.get_cache_dir() == '/foo/rubyvenv'


def test_mocked_cache(mocked_cache):
    assert rubyvenv.get_cache_dir() == mocked_cache.strpath


def _fileobj_func(contents):
    def func():
        return io.BytesIO(contents)
    return func


class BoomError(RuntimeError):
    pass


class RaisesAfterSomeIO(object):
    def __init__(self):
        self.until_boom = 3

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, size):
        if self.until_boom:
            self.until_boom -= 1
            return b'tick tock!\n'
        else:
            raise BoomError()


def test_ensure_cache_file_file_exists(mocked_cache):
    cache_file = mocked_cache.ensure_dir().join('test.txt')
    cache_file.write('foo')
    ret = rubyvenv.ensure_cache_file('test.txt', _fileobj_func(b'bar'))
    assert ret == cache_file.strpath
    assert cache_file.read() == 'foo'


def test_ensure_cache_file_file_does_not_exist(mocked_cache):
    cache_file = mocked_cache.join('test.txt')
    ret = rubyvenv.ensure_cache_file('test.txt', _fileobj_func(b'bar'))
    assert ret == cache_file.strpath
    assert cache_file.read() == 'bar'


def test_ensure_cache_file_makes_directories(mocked_cache):
    cache_file = mocked_cache.join('dir/test.txt')
    ret = rubyvenv.ensure_cache_file('dir/test.txt', _fileobj_func(b'bar'))
    assert ret == cache_file.strpath
    assert cache_file.read() == 'bar'


def test_ensure_cache_exception_safety(mocked_cache):
    cache_file = mocked_cache.join('test.txt')
    with pytest.raises(BoomError):
        rubyvenv.ensure_cache_file('test.txt', RaisesAfterSomeIO)
    assert not cache_file.exists()
    assert mocked_cache.join('tmp').listdir() == []


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


def test_version_to_filename():
    assert rubyvenv._version_to_filename('1.2.3') == 'ruby-1.2.3.tar.bz2'


def test_version_to_filename_filename_to_version_roundtrip():
    version = '1.2.3'
    ret = version
    ret = rubyvenv._version_to_filename(ret)
    ret = rubyvenv._filename_to_version(ret)
    assert ret == version


@pytest.yield_fixture
def xenial():
    with mock.patch.object(platform, 'machine', return_value='x86_64'):
        with mock.patch.object(distro, 'id', return_value='ubuntu'):
            with mock.patch.object(distro, 'version', return_value='16.04'):
                yield


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


@pytest.mark.usefixtures('xenial')
def test_pick_version_version_specified():
    assert rubyvenv.pick_version('2.3.0') == rubyvenv.Version(
        '2.3.0',
        'https://rvm.io/binaries/ubuntu/16.04/x86_64/ruby-2.3.0.tar.bz2',
    )


@pytest.mark.usefixtures('xenial', 'returns_xenial')
def test_pick_version_latest():
    assert rubyvenv.pick_version('latest') == rubyvenv.Version(
        '2.3.1',
        'https://rvm.io/binaries/ubuntu/16.04/x86_64/ruby-2.3.1.tar.bz2',
    )


def test_missing_dest_dir(capsys):
    with pytest.raises(SystemExit):
        rubyvenv.main(())
    out, err = capsys.readouterr()
    assert 'DEST_DIR is required' in out + err


def _run(env, sh):
    return subprocess.check_output((
        'bash', '-euc',
        'PS1="$ "; . {env}/bin/activate; {sh}'.format(env=env, sh=sh),
    )).decode('UTF-8')


@pytest.mark.usefixtures('mocked_cache')
def test_integration(tmpdir):
    env = tmpdir.join('rubyvenv')
    assert not rubyvenv.main((env.strpath,))

    assert _run(env, 'echo $RUBYVENV') == env + '\n'
    assert _run(env, 'which ruby') == env.join('bin/ruby') + '\n'
    assert _run(env, 'which gem') == env.join('bin/gem') + '\n'

    _run(env, 'gem install sass --no-ri --no-rdoc')
    assert _run(env, 'which sass') == env.join('bin/sass') + '\n'


def test_integration_system(tmpdir):
    env = tmpdir.join('rubyvenv')
    assert not rubyvenv.main((env.strpath, '--ruby', 'system'))

    _run(env, 'gem install sass --no-ri --no-rdoc')
    assert _run(env, 'which sass') == env.join('lib/gems/bin/sass') + '\n'
