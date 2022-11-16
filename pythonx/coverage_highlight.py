"""
" HACK to force-reload it from vim with :source %
pyx import sys; sys.modules.pop("coverage_highlight", None); import coverage_highlight
finish
"""
import os
import shlex
import subprocess
import vim
import json


def get_verbosity():
    return int(vim.eval('&verbose'))


def get_cmdheight():
    return int(vim.eval('&cmdheight'))


def get_wrapscan():
    return int(vim.eval('&wrapscan'))


def debug(msg):
    if get_verbosity() >= 2:
        print(msg)


def error(msg):
    vim.command("echohl ErrorMsg")
    vim.command("echomsg '%s'" % msg.replace("'", "''"))
    vim.command("echohl None")


class Signs(object):

    first_sign_id = 17474  # random number to avoid clashes with other plugins

    def __init__(self, buf=None):
        if buf is None:
            buf = vim.current.buffer
        self.buffer = buf
        self.bufferid = buf.number
        # convert vim.List() to a regular list
        self.signs = list(buf.vars.get(
            'coverage-highlight.vim:coverage_signs', []))
        self.signid = max(self.signs) if self.signs else self.first_sign_id
        # convert vim.Dictionary() to a regular dictionary
        # convert keys to ints (vim.Dictionary() only allows string keys)
        # convert values from vim.List() to regular lists
        # convert list values from bytes to unicode (on Python 3)
        self.last_row = buf.vars.get('coverage-highlight.vim:last_row', 0)
        self.last_row_signs = list(buf.vars.get(
            'coverage-highlight.vim:last_row_signs', []))

    @classmethod
    def for_file(cls, filename):
        for buf in vim.buffers:
            try:
                if os.path.samefile(buf.name, filename):
                    return cls(buf)
            except (OSError, IOError):
                pass

    def _place(self, signs, lineno, name):
        self.signid += 1
        cmd = "sign place %d line=%d name=%s buffer=%s" % (
            self.signid, lineno, name, self.bufferid)
        vim.command(cmd)
        signs.append(self.signid)

    def place(self, lineno, name='NoCoverage'):
        self._place(self.signs, lineno, name)


    def clear(self):
        for sign in self.signs:
            cmd = "sign unplace %d" % sign
            vim.command(cmd)
        self.signs = []
        self.clear_last_row_signs()

    def clear_last_row_signs(self):
        for sign in self.last_row_signs:
            cmd = "sign unplace %d" % sign
            vim.command(cmd)
        self.last_row_signs = []

    def save(self):
        self.buffer.vars['coverage-highlight.vim:coverage_signs'] = self.signs
        self.save_last_row()

    def save_last_row(self):
        self.buffer.vars['coverage-highlight.vim:last_row'] = self.last_row
        self.buffer.vars['coverage-highlight.vim:last_row_signs'] = (
            self.last_row_signs
        )

def lazyredraw(fn):
    def wrapped(*args, **kw):
        oldvalue = vim.eval('&lazyredraw')
        try:
            vim.command('set lazyredraw')
            return fn(*args, **kw)
        finally:
            vim.command('let &lazyredraw = %s' % oldvalue)
    return wrapped


def parse_full_coverage_output(output, coverage_dir):
    if not output and get_verbosity() >= 1:
        print("Got no output!")
        return

    for module,filename in output['moduleMap'].items():
        filename = os.path.relpath(os.path.join(coverage_dir, filename))
        if not os.path.exists(filename):
            # this is unexpected
            if get_verbosity() >= 1:
                print("Skipping %s: no such file" % filename)
            continue
        signs = Signs.for_file(filename)
        if signs is None:
            # Vim can't place signs on files that are not loaded into buffers
            if get_verbosity() >= 1:
                print("Skipping %s: not loaded in any buffer" % filename)
            continue

        signs.clear()
        parse_lines(filename, output['coverageData'][module], signs)
        signs.save()

    if get_verbosity() >= 1:
        print("Done parsing coverage!")


@lazyredraw
def parse_lines(filename, spans, signs):
    for span in spans:
        if 'count' in span:
            continue # it has _some_ coverage

        line_from = span['from']['line']
        line_to = span['to']['line']

        for lineno in range(line_from, line_to+1):
            signs.place(lineno)


def program_in_path(program):
    path = os.environ.get("PATH", os.defpath).split(os.pathsep)
    return any(os.path.isfile(os.path.join(dir, program)) for dir in path)


def find_coverage_bin():
    override = vim.eval('g:elm_coverage_binary')
    if override:
        return override
    if program_in_path('elm-coverage'):
        # assume it was installed
        return 'elm-coverage'


def find_coverage_dir(filename):
    if os.path.exists('.coverage'):
        return '.'
    where = os.path.dirname(filename)
    while True:
        if os.path.exists(os.path.join(where, '.coverage')):
            debug("Found %s" % os.path.join(where, '.coverage'))
            return where or os.curdir
        if os.path.dirname(where) == where:
            debug("Did not find .coverage in any parent directory, defaulting to .")
            return '.'
        where = os.path.dirname(where)


def run_coverage_report(coverage_bin, coverage_dir, args=[]):
    if get_cmdheight() > 1 or get_verbosity() >= 1:
        print("Running %s -r codecov %s" % (
            os.path.relpath(coverage_bin), ' '.join(args)))
        if get_verbosity() >= 2:
            print("in %s" % coverage_dir)
    if os.path.exists(coverage_bin):
        command = [os.path.abspath(coverage_bin)]
    else:
        # things like "python3 -m coverage"
        command = shlex.split(coverage_bin)
    stdout = subprocess.Popen(command + ['-r','codecov'] + args,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT,
                              cwd=coverage_dir).communicate()[0]
    if not isinstance(stdout, str):
        stdout = stdout.decode('UTF-8', 'replace')
    # print(stdout)


def clear(clear_total=True):
    signs = Signs()
    signs.clear()
    signs.save()

def highlight(force=False):
    coverage_bin = find_coverage_bin()
    if not coverage_bin:
        error("Could not find the 'elm-coverage' binary.")
        return
    filename = vim.current.buffer.name
    coverage_dir = find_coverage_dir(filename)
    coverage_report = os.path.join(coverage_dir, '.coverage', 'codecov.json')
    
    if force or not os.path.exists(coverage_report):
        run_coverage_report(coverage_bin, coverage_dir)

    with open(coverage_report, 'r') as report:
        output = json.load(report)

    clear(clear_total=False)
    parse_full_coverage_output(output, coverage_dir)
    cursor_moved(force=True)

def highlight_all():
    highlight(force=False)

def highlight_redo():
    highlight(force=True)

def cursor_moved(force=False):
    signs = Signs()
    row, col = vim.current.window.cursor
    if row != signs.last_row or force:
        signs.clear_last_row_signs()
        signs.last_row = row
        signs.save_last_row()
