#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    migrate
    ~~~~~~~
    A simple generic database migration tool

    :copyright: (c) 2014 Francis Asante <kofrasa@gmail.com>
    :license: MIT
"""

__version__ = '0.2.2'

import os
import sys
import argparse
import glob
import subprocess
from ConfigParser import ConfigParser
from datetime import datetime


COMMANDS = {
    'postgres': "psql --host {host} --port {port} --username {user} -d {database}",
    'mysql': "mysql --host {host} --port {port} --user {user} -D {database}",
    'sqlite3': "sqlite3 {database}"
}
PORTS = dict(postgres=5432, mysql=3306)


class Migrate(object):
    """A simple generic database migration helper
    """

    def __init__(self, config):
        if config.get('file'):
            # read ini configuration
            parser = ConfigParser()
            parser.read(config['file'])
            env = config.get('env', 'dev')
            for name in ('engine', 'user', 'password', 'migration_path',
                         'host', 'port', 'database', 'verbose'):
                if parser.has_option(env, name):
                    value = parser.get(env, name)
                    if not value:
                        continue
                    if name == 'migration_path':
                        config['path'] = value
                    else:
                        config[name] = value
        # assign configuration
        self._migration_path = os.path.abspath(config.get('path'))
        self._host = config.get('host')
        self._port = config.get('port')
        self._user = config.get('user')
        self._password = config.get('password')
        self._database = config.get('database')
        self._rev = config.get('rev')
        self._command = config.get('command')
        self._message = config.get('message')
        self._engine = config.get('engine')
        self._verbose = int(config.get('verbose') or '0')
        self._dry_run = config.get('dry_run')
        if self._rev:
            assert self._rev.isdigit(), "Revision must be a valid integer"

        assert os.path.exists(self._migration_path) and os.path.isdir(self._migration_path), \
            "migration folder does not exist: %s" % self._migration_path
        current_dir = os.path.abspath(os.getcwd())
        os.chdir(self._migration_path)
        # cache ordered list of the names of all revision folders
        self._revisions = map(str,
                              sorted(map(int, filter(lambda x: x.isdigit(), glob.glob("*")))))
        os.chdir(current_dir)

    def _log(self, level, msg):
        """Simple logging for the given verbosity level
        """
        if self._verbose >= level:
            print msg

    def _cmd_create(self):
        """Create a migration in the current or new revision folder
        """
        assert self._message, "need to supply a message for the \"create\" command"
        if not self._revisions:
            # we start from revision 1
            self._revisions.append("1")

        # get the migration folder
        rev_folder = self._revisions[-1]
        full_rev_path = os.path.join(self._migration_path, rev_folder)
        if not os.path.exists(full_rev_path):
            os.mkdir(full_rev_path)
        else:
            count = len(glob.glob(os.path.join(full_rev_path, "*")))
            # create next revision folder if needed
            if count and self._rev and int(self._rev) == 0:
                rev_folder = str(int(rev_folder) + 1)
                full_rev_path = os.path.join(self._migration_path, rev_folder)
                os.mkdir(full_rev_path)
                self._revisions.append(rev_folder)

        # format file name with sleep to space out timestamps
        filename = "%s.%s" % (
            datetime.utcnow().strftime("%Y%m%d%H%M%S"),
            '-'.join([s.lower() for s in self._message.split(' ') if s.strip()]))
        # create the migration files
        self._log(0, "creating files: ")
        for s in ('up', 'down'):
            file_path = "%s.%s.sql" % (filename, s)
            with open(os.path.join(full_rev_path, file_path), 'a+') as w:
                w.write("-- %s: %s" % (s.upper(), self._message))
                self._log(0, file_path)

    def _cmd_up(self):
        """Upgrade to a revision
        """
        revision = self._get_revision()
        if not self._rev:
            self._log(0, "upgrading current revision")
        else:
            self._log(0, "upgrading from revision %s" % revision)
        for rev in self._revisions[int(revision) - 1:]:
            sql_files = glob.glob(os.path.join(self._migration_path, rev, "*.up.sql"))
            sql_files.sort()
            self._exec(sql_files)
            self._log(1, "upgraded revision %s" % rev)
        self._log(0, "done!")

    def _cmd_down(self):
        """Downgrade to a revision
        """
        revision = self._get_revision()
        if not self._rev:
            self._log(0, "downgrading current revision")
        else:
            self._log(0, "downgrading to revision %s" % revision)
        # execute from latest to oldest revision
        for rev in reversed(self._revisions[int(revision) - 1:]):
            sql_files = glob.glob(os.path.join(self._migration_path, rev, "*.down.sql"))
            sql_files.sort(reverse=True)
            self._exec(sql_files)
            self._log(1, "downgraded revision %s" % rev)
        self._log(0, "done!")

    def _cmd_refresh(self):
        """Downgrade and re-run revisions
        """
        self._cmd_down()
        self._cmd_up()

    def _get_revision(self):
        """Validate and return the revision to use for current command
        """
        assert self._revisions, "no migration revision exist"
        revision = self._rev or self._revisions[-1]
        # revision count must be less or equal since revisions are ordered
        assert revision in self._revisions, "invalid revision specified"
        return revision

    def _get_command(self, **kwargs):
        return COMMANDS[self._engine].format(**kwargs) if kwargs else \
            COMMANDS[self._engine].split()[0]

    def _exec(self, files):
        if self._password and self._password is True:
            import getpass
            # cache password for later use
            self._password = getpass.getpass()

        cmd = self._get_command(
            host=self._host,
            user=self._user,
            database=self._database,
            port=self._port or PORTS.get(self._engine, None))

        func = globals()["exec_%s" % self._engine]
        try:
            assert callable(func), "no exec function found for " + self._engine
            for f in files:
                self._log(1, "applying: %s" % os.path.basename(f))
                if not self._dry_run:
                    func(cmd, f, self._password)
                else:
                    print
                    with open(f, 'r') as fd:
                        for line in fd:
                            print line.strip()
        except Exception as e:
            print >> sys.stderr, str(e)

    def run(self):
        try:
            # check for availability of target command line tool
            cmd_name = self._get_command()
            cmd_path = subprocess.check_output(["which", cmd_name]).strip()
            assert os.path.exists(cmd_path), "no %s command found on path" % cmd_name
            {
                'create': lambda: self._cmd_create(),
                'up': lambda: self._cmd_up(),
                'down': lambda: self._cmd_down(),
                'refresh': lambda: self._cmd_refresh()
            }.get(self._command)()
        except Exception as e:
            print >> sys.stderr, str(e)


def exec_mysql(cmd, filename, password=None):
    if password:
        cmd = cmd + ' -p' + password
    with open(filename) as f:
        return subprocess.call(cmd.split(), stdin=f)

# reuse :)
exec_sqlite3 = lambda a, b, c: exec_mysql(a, b, None)


def exec_postgres(cmd, filename, password=None):
    # psql tool will read the password from the system environment
    env_password = None
    if password:
        # backup any existing password
        env_password = subprocess.check_output(['echo', '$PGPASSWORD'])
        subprocess.call(['export', 'PGPASSWORD=' + password])
    try:
        return subprocess.call(cmd.split() + ['-f', filename])
    finally:
        if env_password:
            # restore password
            subprocess.call(['export', 'PGPASSWORD=' + env_password])
        else:
            subprocess.call(['unset', 'PGPASSWORD'])


def main():
    login_name = os.getlogin()
    migration_path = os.path.join(os.getcwd(), "migrations")

    parser = argparse.ArgumentParser(
        prog=os.path.split(__file__)[1],
        description="A simple generic database migration tool using SQL scripts",
        usage="%(prog)s <command> [options]")
    parser.add_argument(dest='command', default='create',
                        choices=('create', 'up', 'down', 'refresh'),
                        help='command (default: "create")')
    parser.add_argument("-e", dest="engine", default='sqlite3',
                        choices=('postgres', 'mysql', 'sqlite3'),
                        help="database engine (default: \"sqlite3\")")
    parser.add_argument("-r", dest="rev",
                        help="revision to use. specify \"0\" for the next revision if using the "
                             "\"create\" command. (default: last revision)")
    parser.add_argument("-m", dest="message",
                        help="message description for migrations created with the "
                             "\"create\" command")
    parser.add_argument("-u", dest="user", default=login_name,
                        help="database user name (default: \"%s\")" % login_name)
    parser.add_argument("-p", dest="password", action='store_true', default=False,
                        help="prompt for database password. "
                             "if not supplied assumes no password unless read from config.")
    parser.add_argument("--host", default="localhost",
                        help='database server host (default: "localhost")')
    parser.add_argument("--port",
                        help='server port (default: postgres=5432, mysql=3306)')
    parser.add_argument("-d", dest="database", default=login_name,
                        help="database name to use. specify a /path/to/file if using sqlite3. "
                             "(default: login name)")
    parser.add_argument("--path", default=migration_path,
                        help="path to the migration folder either absolute or relative to the "
                             "current directory. (default: \"./migrations\")")
    parser.add_argument("-f", dest='file', metavar='CONFIG',
                        help="configuration file in \".ini\" format. "
                             "Sections represent configurations for different environments. "
                             "Keys include (migration_path, user, password, host, port, "
                             "database, engine)")
    parser.add_argument("--env", default='dev',
                        help="configuration environment. used only with config file as the "
                             "given sections (default: \"dev\")")
    parser.add_argument("--dry-run", action='store_true',
                        help="prints the SQL but does not run it.")
    parser.add_argument("-v", dest="verbose", action='count', default=0,
                        help="show verbose output.")
    parser.add_argument('-V', '--version', action='version',
                        version="%(prog)s " + __version__,
                        help="print version information and exit")

    config = {}
    args = parser.parse_args()
    for name in ('engine', 'command', 'rev', 'password', 'user', 'path', 'env',
                 'host', 'port', 'database', 'file', 'message', 'verbose', 'dry_run'):
        config[name] = getattr(args, name)

    try:
        Migrate(config).run()
    except Exception as e:
        print >> sys.stderr, str(e)
        parser.print_usage(sys.stderr)


if __name__ == '__main__':
    main()