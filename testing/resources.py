import os.path


HERE = os.path.abspath(os.path.dirname(__file__))


def resource(*path):
    return os.path.join(HERE, *path)
