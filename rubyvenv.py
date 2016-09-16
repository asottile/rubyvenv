from __future__ import absolute_import
from __future__ import unicode_literals

import os.path


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
