"""
testflo is a python testing framework that takes an iterator of test
specifier names e.g., <test_module>:<testcase>.<test_method>, and feeds
them through a pipeline of iterators that operate on them and transform them
into TestResult objects, then pass them on to other objects in the pipeline.

The objects passed through the pipline are either strings that
indicate which test to run (I call them test specifiers), or TestReult
objects, which contain only the test specifier string, a status indicating
whether the test passed or failed, and captured stderr from the
running of the test.

The API necessary for objects that participate in the pipeline is a callable
that takes an input iterator and returns an output iterator.

"""

import os
import time

from fnmatch import fnmatch
from argparse import ArgumentParser
from multiprocessing import cpu_count

from testflo.runner import TestRunner
from testflo.result import ResultPrinter, ResultSummary
from testflo.discover import TestDiscoverer, dryrun
from testflo.timefilt import TimeFilter

from testflo.fileutil import read_config_file, read_test_file


def _get_parser():
    """Returns a parser to handle command line args."""

    parser = ArgumentParser()
    parser.usage = "testease [options]"
    parser.add_argument('-c', '--config', action='store', dest='cfg',
                        metavar='CONFIG',
                        help='Path of config file where preferences are specified.')
    parser.add_argument('-t', '--testfile', action='store', dest='testfile',
                        metavar='TESTFILE',
                        help='Path to a file containing one testspec per line.')
    parser.add_argument('--maxtime', action='store', dest='maxtime',
                        metavar='TIME_LIMIT', default=-1, type=float,
                        help='Specifies a time limit for tests to be saved to '
                             'the quicktests.in file.')
    parser.add_argument('-n', '--numprocs', type=int, action='store',
                        dest='num_procs', metavar='NUM_PROCS', default=cpu_count(),
                        help='Number of processes to run. By default, this will '
                             'use the number of CPUs available.  To force serial'
                             ' execution, specify a value of 1.')
    parser.add_argument('-o', '--outfile', action='store', dest='outfile',
                        metavar='OUTFILE', default='test_report.out',
                        help='Name of test report file')
    parser.add_argument('-v', '--verbose', action='store_true', dest='verbose',
                        help='if true, include testspec and elapsed time in '
                             'screen output')
    parser.add_argument('--dryrun', action='store_true', dest='dryrun',
                        help="if true, don't actually run tests, but report"
                          "which tests would have been run")
    parser.add_argument('-x', '--stop', action='store_true', dest='stop',
                        help="if true, stop after the first test failure")
    parser.add_argument('-s', '--nocapture', action='store_true', dest='nocapture',
                        help="if true, stdout will not be captured and will be"
                             " written to the screen immediately")
    parser.add_argument('tests', metavar='test', nargs='*',
                       help='a test method/case/module/directory to run')

    return parser

def run_pipeline(source, pipe):
    """Run a pipeline of test iteration objects."""

    global _start_time
    _start_time = time.time()

    iters = [source]

    # give each object the iterator from upstream in the pipeline
    for i,p in enumerate(pipe):
        iters.append(p(iters[i]))

    # iterate over the last iter in the pipline and we're done
    for result in iters[-1]:
        pass

def main():
    options = _get_parser().parse_args()

    options.skip_dirs = []

    # read user prefs from ~/.testflo file.  create one if it
    # isn't there
    homedir = os.path.expanduser('~')
    rcfile = os.path.join(homedir, '.testflo')
    if not os.path.isfile(rcfile):
        with open(rcfile, 'w') as f:
            f.write("""[testflo]
skip_dirs=site-packages,
    dist-packages,
    build,
    contrib
""" )
    read_config_file(rcfile, options)
    if options.cfg:
        read_config_file(options.cfg, options)

    tests = options.tests
    if options.testfile:
        tests += list(read_test_file(options.testfile))

    if not tests:
        tests = [os.getcwd()]

    def dir_exclude(d):
        for skip in options.skip_dirs:
            if fnmatch(os.path.basename(d), skip):
                return True
        return False

    with open(options.outfile, 'w') as report:
        pipeline = [
            TestDiscoverer(dir_exclude=dir_exclude).get_iter,
        ]

        if options.dryrun:
            pipeline.extend(
                [
                    dryrun,
                ]
            )
        else:
            pipeline.extend(
            [
                TestRunner(options).get_iter,
                ResultPrinter(verbose=options.verbose).get_iter,
                ResultSummary().get_iter,

                # mirror results and summary to a report file
                ResultPrinter(report, verbose=options.verbose).get_iter,
                ResultSummary(report).get_iter,
            ])

        if options.maxtime > 0:
            pipeline.append(TimeFilter(options.maxtime).get_iter)

        run_pipeline(tests, pipeline)


if __name__ == '__main__':
    main()
