#! /usr/bin/env python
"""IDPOOL tester

This is a simple test script to make sure the IDpool class works correctly

"""

import common.IDpool as IDpool

pool = IDpool.getID('Test-pool2',verbose=True)  # creates an IDpool object and draws out an ID from the pool,
                                # starting a new pool if one doesn't already exist.

print 'My ID number is: ' + str(pool.ID)
