"""Reverse probe: omit older backups, observe regression, restore and pass.

Run from the repository root: python scripts/probe_recover_history.py
Only synthetic tests run; the implementation and source files are not modified.
"""
import unittest

import recover_history as recovery
import test_recover_history as tests


def main():
    original = recovery.merge
    try:
        recovery.merge = lambda documents: original(documents[-1:])
        red = unittest.TextTestRunner(verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromName(
                "RecoveryTests.test_union_keeps_older_backup_orders_and_current_wins", tests))
    finally:
        recovery.merge = original
    if red.wasSuccessful() or red.errors or len(red.failures) != 1:
        print("Reverse probe failed: expected exactly one regression assertion.")
        return 1
    print("RED: omitting older backups loses the oldest point.")
    green = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
    if not green.wasSuccessful():
        return 1
    print("GREEN: restored union; all recovery tests pass.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
