'''
Language agnostic database migration tool

migrate
=======

A simple language agnostic database migration tool

install
-------
::

    $ pip install migrate

usage
-----
::

    usage: migrate [options] <command>

See Readme_

.. _Readme: https://github.com/migrate/migrate/blob/master/README.md
'''

import migrate3
from setuptools import setup

setup(
    name='migrate3',
    version=migrate3.__version__,
    license='MIT',
    author='Francis Asante',
    author_email='kofrasa@gmail.com',
    url='https://github.com/mylokin/migrate',
    description='A simple language agnostic database migration tool',
    long_description=__doc__,
    py_modules=['migrate3'],
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.4',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Operating System :: POSIX',
        'License :: OSI Approved :: MIT License',
        'Topic :: Software Development :: Libraries',
        'Topic :: Database',
        'Topic :: Utilities'
    ],
    entry_points={
        'console_scripts': ['migrate=migrate3:main']
    },
    test_suite = 'test_migrate',
)
