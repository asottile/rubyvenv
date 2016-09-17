from setuptools import setup

setup(
    name='rubyvenv',
    description=(
        'Create no-hassle ruby "virtualenvs".  '
        'No .bashrc, no shims, no cd-magic.'
    ),
    url='https://github.com/asottile/rubyvenv',
    version='0.0.0',
    author='Anthony Sottile',
    author_email='asottile@umich.edu',
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
    ],
    py_modules=['rubyvenv'],
    install_requires=['distro', 'six'],
    entry_points={'console_scripts': ['rubyvenv = rubyvenv:main']},
)
