
"""
This is meant to be executed using mpirun.  It is called as a subprocess
to run an MPI test.

"""

exit_codes = {
    'OK': 0,
    'SKIP': 42,
    'FAIL': 43,
}

if __name__ == '__main__':
    import sys
    import os
    import traceback

    from mpi4py import MPI
    from testflo.test import Test
    from testflo.cover import save_coverage
    from testflo.qman import get_client_manager
    from testflo.util import get_addr_auth_from_args

    exitcode = 0  # use 0 for exit code of all ranks != 0 because otherwise,
                  # MPI will terminate other processes

    address, authkey = get_addr_auth_from_args(sys.argv[2:])

    manager = get_client_manager(address, authkey)
    q = None

    try:
        try:
            comm = MPI.COMM_WORLD
            test = Test(sys.argv[1])
            test.run()
        except:
            print(traceback.format_exc())
            test.status = 'FAIL'
            test.err_msg = traceback.format_exc()

        # collect results
        results = comm.gather(test, root=0)
        if comm.rank == 0:
            q = manager.get_queue()

            total_mem_usage = sum(r.memory_usage for r in results)
            test.memory_usage = total_mem_usage

            # check for errors and record error message
            for r in results:
                if r.status != 'OK':
                    test.err_msg = r.err_msg
                    test.status = 'FAIL'
                    exitcode = exit_codes[r.status]
                    break

        save_coverage()

    except Exception:
        test.err_msg = traceback.format_exc()
        test.status = 'FAIL'
        exitcode = exit_codes['FAIL']

    finally:
        sys.stdout.flush()
        sys.stderr.flush()

        if comm.rank == 0 and q is not None:
            q.put(test)

        sys.exit(exitcode)
