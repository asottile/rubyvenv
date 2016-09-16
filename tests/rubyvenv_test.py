from __future__ import absolute_import
from __future__ import unicode_literals

import os

import mock

from rubyvenv import cache_dir
from rubyvenv import mkdirp


def test_cache_dir_xdg_variable():
    with mock.patch.dict(os.environ, {'XDG_CACHE_HOME': '/foo'}):
        assert cache_dir() == '/foo/rubyvenv'


def test_mkdirp(tmpdir):
    path = tmpdir.join('foo/bar')
    assert not path.exists()
    mkdirp(path.strpath)
    assert path.isdir()
    mkdirp(path.strpath)
