import os
import platform
import time
import errno
from pathutils import Lock #for file locking

class getID:
    """Parallel ID checkout class
    
    This is a simple class to allow multiple processes running in parallel
    to check out an ID number based on a file which keeps a log of the 
    previously checked out ID's. For use when the parallel processes are run
    by a seperate program and we just want to avoid those processes having file
    clashes and such in the python part.

    The main point is to define self.ID, which will be a unique string
    identifying this process (an integer).
    """
            
    def __init__(self,jobID=None,verbose=False,MPIrank=None):
        """Initialises the object and creates the pool file (unless the file
        has already been created by another process)
        
        Keyword Args:
        
        jobID -- a unique identifier for the current job so that if a previous
        pool file has not been cleaned up then the current job knows to just
        overwrite it.
        verbose -- set to True for debugging output
        MPIrank -- If python is handling the MPI initialisation then we can just
        use the mpi rank rather than the IDpool checkout system.
        """
        fname = 'IDpool-{0}.log'.format(jobID)
        if MPIrank!=None:
            print 'Using MPIrank as job ID number:', MPIrank
            self.ID = MPIrank
            print 'checkpoint idpool 1'
            f = open(fname,'w')
            f.write('{0} - {1}\n'.format(self.ID,platform.node()))
            #f.write('{0} - {1}\n'.format(self.ID,'test'))
            print 'checkpoint idpool 2'
        else:
            print 'No MPIrank received, initalising IDpool file'
            #use the IDpool checkout system as a backup
            if verbose: print 'START'
            lock = Lock(fname,timeout=120,step=1)   #lock the filename before we even try to open it, to prevent other processes sneaking in and accessing it in the gap we would leave otherwise
            lock.lock(force=False)
            if verbose: print 'Lock acquired'
            try:
                f = open(fname,'r+')     #try to open file, will fail if it does not already exist
            except IOError, e:  #if file fails to open, make sure it is because it doesn't exist and then create it
                if e.errno == errno.ENOENT:
                    f = open(fname,'w')
                    if verbose: print 'Starting new log file'
                    #Start a new log file
                    f.write('{0}\n'.format(jobID))                 # first line is the jobID
                    f.write('0 - {0}\n'.format(platform.node()))   # checkout line, an integer and the name of the node which checked it out
                    self.ID = 0 #check out the first ID and exit
                    f.close()   #close the file
                    lock.unlock()   #release the lock
                    return  #we are done!
                    
            #if the file already exists, loop to the end to determine the next number to log out
            for i,line in enumerate(f):    #string will be empty only when EOF is reached
                thisline = line
            # end loop: we just let the loop finish because we only care about the last line of the file to figure
            # out what the next ID should be
            # print 'HERE100: '+thisline
            l = thisline.partition(' - ')       #split the last line of the file into the ID, the separator and the node name
            if verbose: print l
            self.ID = int(l[0]) + 1         #take the last ID checked out, add 1, and set this as the ID for the current process.
            # write a new line to file recording the newly checked out ID
            f.write('{0} - {1}\n'.format(self.ID,platform.node()))
            f.close()       #close file
            lock.unlock()   #release the lock
    
