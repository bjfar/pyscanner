#! /usr/bin/env python
"""MAIN PYSUSY RUNSEQUENCE

This module is the main executable for pysusy. Its instructions are stored
in a number of setup scripts which are listed below, which are to be
specified in the MASTER config file. Pysusy may be run from the command line
or from within the interpreter.
Because functions must be defined before they are called, the order of functions
listed here is almost the reverse of the order they are called. To best read the
code go to the end of this file and read the commands actually executed when
the script is invoked, then work upwards through each function as it is called.

Command line usage:

python pysusy.py [MASTER config module name] [Job ID string] [extra run options]

OR

./pysusy.py [MASTER config module name] [Job ID string] [extra run options]

The "extra run options" arguments are passed to the master configuration script,
they allow the user to set extra configuration options at runtime. Of course the
user must tell the master configuration script what to do with these arguments.

Note: [MASTER config module name] can refer to a submodule, i.e. if you organise
your config files into a python package structure, say put them within a directory
called 'master' and name the config file 'Mconfig', then the argument given should
be 'master.Mconfig'.
"""

# Import external modules
#bjf> CHECK IF ALL THESE ARE NEEDED!
print 'checkpoint'
import os
import sys
import shutil
import time
import tarfile      #use for creating tar archives
#import inspect      #need to get information about modules and objects (like what file they are defined in)

#import glob
#import getopt
from common.extra import BadModelPointError
# Import timing module (for testing)
from common.timing import print_timing

#import datetime     #time and date handling
from collections import OrderedDict as Odict #ordered dictionary (needs python 2.7+)

print 'checkpoint2'
#import scipy as sp
print 'checkpoint3'
import numpy as np
print 'checkpoint4'
# Import MULTINEST extension module (must be installed)
from multinest import nestwrapper   
print 'checkpoint10'
# Import PYSUSY modules
from common.listsampler import listwrapper #List sampling driver
print 'checkpoint9'

#Import MPI module
from mpi4py import MPI
print 'checkpoint10'

class Usage(Exception):
    def __init__(self, msg):
        self.msg = msg
        
class odict(Odict):
    """Modified Ordered Dictionary"""
    def setvalues(self,list):
        """Assign 'list' to the values of the dictionary, in the order
        defined by the ordering of the dictionary"""
        #print list
        for i,key in enumerate(self.keys()):
            self[key] = list[i]
        
def initMPI():
    """Initialise MPI bindings
    If MPI is being handled by this wrapper (rather than by the 
    parameter generator code) we perform these initialisations.
    """
    print 'Initializing MPI bindings...'
    #MPI initializations
    #call MPI_INIT(errcode)
    comm = MPI.COMM_WORLD
    #if errcode!=MPI_SUCCESS:
            #print 'Error starting MPI. Terminating.'
            #call MPI_ABORT(MPI_COMM_WORLD,errcode)

    rank = comm.Get_rank()
    size = comm.Get_size()
    #bjf> debugging
    print 'MPI info:', 'comm:',comm, 'rank:', rank,'size:', size
    #give this rank to SUSYFILE class, it handles the job file stamping (naming),
    #needs to know this to stamp files accordingly
    return comm, rank, size
    
class Scan:
    """Main PyScanner class. Used to set up a scan for running."""
    
    def writeinfofiles(self,obsdict,likedict):
        line = '\
---------------------------------------------------------------------\n'
        #create parameter info file
        print 'WRITING PARAMETER INFO FILE'
        FILE = open(self.outputpathbasename+'.info', 'w')               #open the info file to write the names of the output columns
        #This output generated using the master configuration module {0}\n\.format(self.masterconfig)
        txt = '\
This file records the info about what is stored in each column\n\
of the .txt output file for this job \n\
Column  1: Posterior probability weight \n\
Column  2: -2*Log(Likelihood) (aka chi^2) \n'
        i = 3
        for param in self.cubedict.keys():
            txt += 'Column {0:2}: {1:10s} \n'.format(i,param)
            i += 1
        for program,dict in obsdict.items():
            for obs in dict.keys():
                txt += 'Column {0:2}: {1:10s} \n'.format(i,program+'-'+obs)
                i += 1
        for like in likedict.keys():
            txt += 'Column {0:2}: logl-{1:10s} \n'.format(i,like)
            i += 1
        FILE.write(txt)
        
        #create timing info file
        print 'WRITING TIMING INFO FILE'
        FILE = open(self.outputpathbasename+'.timinginfo', 'w')         #open the info file to write the names of the output columns
        txt = '\
This file records the info about what is stored in each column\n\
of the .timing output file for this job \n\
Column  1: neg2LogL \n'
        i = 2
        for param in self.cubedict.keys():
            txt += 'Column {0:2}: {1:10s} \n'.format(i,param)
            i += 1
        txt += '\
Column  {0}: Total time of loop \n\
Column  {1}: Total time between this start of this loop and end of previous loop (sampler time)\n\
Column  {2}: Time spent computing likelihood function \n'.format(i,i+1,i+2)
        i += 3
        for program,dict in obsdict.items():
            for obs in dict.keys():
                txt += 'Column {0:2}: {1:10s} \n'.format(i,program+'-'+obs)
                i += 1
        for like in likedict.keys():
            txt += 'Column {0:2}: logl-{1:10s} \n'.format(i,like)
            i += 1
        txt += '\n\
Remaining columns contain data from timing list'
        FILE.write(txt)

        #create notes file (just for extra notes about the run) 
        print 'WRITING NOTES FILE'
        txt = 'This file records extra notes about the run.\n\n'
        FILEnotes = open(self.outputpathbasename+'.notes', 'w')         #open the info file to write the names of the output columns
        unusedlikes = [like for like,(logl,uselike) in likedict.items() if uselike==False] #compiles a list of likelihoods whose 'uselike' parameter is set to False. These likelihood function components have not been folded into the scan.
        if unusedlikes:                                                    #do this if the list uselikes is non-empty
            txt += '\
The following likelihood functions components have NOT been \n\
folded into the scan ("uselike" parameters were set to False). The\n\
computed likelihood values are however supplied in the scan output\n\
for post-scan analysis:\n'
            txt += line
            for likename in unusedlikes:
                txt += 'logl-{0}\n'.format(likename)
            txt += line
            FILEnotes.write(txt)
            
    def stringifyline(self,lst):
        line = []
        for item in lst:
            try:
                line += ['{0:< 10.5g}'.format(item)]
            except ValueError:
                line += [str(item)]
        return ' '.join(line)+'\n'
    
    def writetiminginfo(self,timingbuffer):
        ftime = open(self.outputpathbasename+'.timing','a')             #open the info file to write the names of the output columns
        txt = ''
        for timinginfo in timingbuffer:
            txt += self.stringifyline(timinginfo)                       #generate line of
        ftime.write(txt)                                                #output lines to file
        ftime.close()
               
    def getloglike(self,cube):
        """Likelihood wrapper function
        Receive 'cube' from the parameter generator, feed it into the 
        Simulator (i.e. run the program sequence) and return the scaled 
        parameters in 'cube' as well as the log likelihood value of the 
        input point.
        Args:
        cube -- the vector of points sampled uniformly from a (0,1) cube
            of size 'ndims' 
        """
        #I don't want to trust Multinest
        
        #----Measure how much time was just spent in the sampler code---
        self.prevtmsamp = self.tmsamp                                   #get starting time for sampler
        self.tmsamp = time.time()                                       #get finishing time for sampler   
        samptime = (self.tmsamp-self.prevtmsamp)*1000
        
        #---Scale unit 'cube' up into the parameter vector using prior--
        self.cubedict.setvalues(cube[:self.npars])                      #returns a dictionary of the parameter values modified to the scaled valued, based on the prior function
        paramvector = self.cubedict if self.skipprior else self.prior(self.cubedict)
        if self.printing: print "paramvector:", paramvector
 
        #---Put the scaled parameters back into cube--------------------
        cube[:self.npars] = paramvector.values()                        #there should be ndims of these. ndims+x will contain nothing, but later we will store extra output, like observables, in these slots. 
                
        #---Give parameters to Simulator, which computes likelihoods----
        tm1 = time.time() 
        if self.printing: print paramvector
        if self.printingmore: print 'runpoint start'
        try:
            lnew, likedict, obsdict, timelist = self.likefunc(paramvector) #,printing,skipproblems,retry)    #returns the log likelihood of the point 'paramvector'. Set printing to true to see output.
        except BadModelPointError, err:
            #sys.stderr.write('BADMODELPOINTERROR')
            lnew = -1e300                                               #if such an error is encountered we want to set the logl value for this point to the minimum value (exclude point)
            likedict = {}                                               #set other output to empty
            obsdict = {}
            timelist = [err]                                            #store the error message in the timing output file for later consideration
        if self.printingmore: print 'runpoint end'
                                                                        #likes contains a list of the individual contributions to the likelihood function, so we can see what is important in different places
                                                                        #timelist is a list containing the execution times of the sub-programs, in the order they were executed
        if self.printing: print 'loglikelihood: ', lnew
        #print lnew, cube[:self.npars]
        #print likedict
        #print timelist
    
        if self.printing: print likes
        tm2 = time.time()
        pointtime = (tm2-tm1)*1000                                      #total runtime for runpoint call (ms)
        try:
            pointdiff = pointtime - sum(timelist)                       #difference between runtimes of programs and overall time spent in sim.runpoint (to check python overhead)
        except TypeError:
            pointdiff = -1                                              #if there is an error during the program loop timelist may contain strings (explaining the error), which obviously cannot be summed.
        looptime = (tm2-self.tmloop)*1000                               #time since this point last iteration
        self.tmloop = tm2                                               #reset loop timer
        likes = [logl for (logl,uselike) in likedict.values()]          #read through likedict and extract likelihoods
        observables = [obsval for progdict in obsdict.values() for obsval in progdict.values()] #read through obsdict and extract values
        self.timingbuffer += [[-2*lnew]+list(cube[:self.npars])+[looptime,samptime,pointtime]+observables+likes+timelist]  #add parameter, likelihood, and this timing information to the timing buffer
        
        if self.printing: print 'LOOP ',self.loop,", runpoint time (process {0}) (ms): ".format(self.rank), pointtime
        
        if len(self.timingbuffer)==self.bufferlength:                   #if the buffer reaches the set maximum length, we write the info to file and reset the buffer
            self.writetiminginfo(self.timingbuffer)                     #write timing info to file
            self.timingbuffer = []                                      #reset the buffer

        #---Write computed likelihoods and observables to file----------
        cubelist = observables                                          #add observables to cubelist
        cubelist += likes                                               #add likelihood values to cubelist
        cube[self.npars:self.npars+len(cubelist)] = cubelist            #fill cube with cubelist values
        
        nfilled = self.npars + len(cubelist)
        if nfilled<len(cube): cube[nfilled:] = [0] * (len(cube) - nfilled)  #if we haven't reached the end of cube, set the remaining slots to zero
                                                                        #The extra entries of cube seem to come out of multinest filled with values so small they screw up the multinest output. We replaces these with zeros here to avoid this
        if self.printing: print cube
        
        #if self.loop >= 10:                                            #use this if you want to just test a few points
        #    sys.exit(1)
        
        self.loop += 1                                                  #increment loop counter
        
        #print 'loop:',loops
        #print 'lnew:',lnew
        
        self.tmsamp = time.time() #begin timer for sampler
        #quit()  #testing something, just want to see one loop.
        return cube, lnew
         
    def mnestLogL(self,cube,ndims,npar,context):
        """Likelihood function wrapper for MultiNest
        This is the callback function given to MultiNest (a fortran
        code) via the python extension wrapper.
        Args:
        cube -- the vector of points sampled uniformly from a (0,1) cube
            of size 'ndims' by the parameter generator. There are 
            (npar-ndims) empty slots at the end of this vector for extra
            output.
        ndims -- the number of parameters being scanned
        npar -- the length of cube.
        context -- unknown
        """
        #======================================================
        # MULTINEST RESUME BACK UP
        #======================================================
        # Running on clusters, it occasions that jobs run into their
        # walltime while multinest is trying to write the resume files,
        # corrupting them all. To allow jobs to be manually recovered 
        # from this, I am implementing a system to back up these files 
        # every now and again.
        # FOR NOW this is a terrible hack. Must integrate it more
        # nicely into pysusy in the future.
        backupevery=2000    #perform backups every 10000 likelihood evaluations (of this process)
        if self.rank == 0 and np.mod(self.loop,backupevery) == 0:
            #list of files to backup
            suffixlist = ['resume.dat','phys_live.points','live.points','ev.dat', \
                'stats.dat','summary.txt','post_separate.dat','post_equal_weights.dat', \
                '.txt','.info']
            sourcelist=[self.outputpathbasename+suffix for suffix in suffixlist]
            destlist=[self.outputpathbasename+suffix+'-BACKUP' for suffix in suffixlist]
            #make a copy of each file
            for infile, outfile in zip(sourcelist,destlist):
                try:
                    shutil.copy(infile, outfile)
                except IOError, err:
                    msg = '(IOError - {0}) : File not found, skipping...'.format(err)
        #======================================================
        #We ditch the ndims, npar and context parameters because we
        #keep track of this stuff via the Scan object.
        return self.getloglike(cube)    #returns cube, lnew
 
    def dumper(nSamples, nlive, nPar, physLive, posterior, paramConstr, maxLogLike, logZ):
        """Extra information dump from multinest
        
        This function is sent to multinest as a place for it to dump a series of extra pieces 
        information which it calculates, so that the user has access to it in memory if they
        like. Much of it ends up in output files anyway but this function lets users to things
        to it directly if they want to.
        """
        
        """IDnumber = master.SetupObjects['IDpool'].ID #get ID number for this process
        
        print "DUMPER FUNCTION OUTPUT (PROCESS {0}) START".format(IDnumber)
        print "nSamples = " , nSamples
        
        print physLive
        print physLive[0]
        print physLive[0][0]"""
        
    def __init__(self,outdir,jobname,sampler,sampleroptions,likefunc,prior=None,parorder=None,testing=False,skipproblems=False,mpi=None,maxtestattempts=20):
        """Scan initialisation
        Args:
        outdir -- Directory to store output files
        sampler -- Parameter generator to use. Must be one of 'multinest', 'list'.
        sampleroptions -- Options dictionary for parameter generator
        jobname -- A string to identify the job, so that the seperately running parallel
            processes can function together correctly. This should be unique enough that concurrently
            running jobs can be distinguished, there will be serious problems if two running jobs have the
            same jobname.
        prior -- Function mapping unit hypercube to parameter space
                    Args: 
        parorder -- list of strings matching the keys of 'prior', in the
            order in which the hypercube parameters are to be interpreted.
        likefunc -- Function returning global log-likelihood
        testingIN -- if True activates super-verbose mode. For debugging purposes only.
        skipproblemsIN -- if True skips over various errors that may arise during evaluation of the program
            cycle (tells code to skip problems generating BadModelPointErrors). 
            Use with caution as it may hide serious problems.
        mpi -- list of mpi objects returned by InitMPI, i.e. [comm, rank, size]. User will
            in most cases need to initialise MPI from the script which initialises the scanner.
            If mpi=None then we initialise MPI here.
	maxtestattempts -- Maximum number of times a BadModelPointError is allowed to occur during test running of the likelihood function (done before scan to determine number of 'cube' slots needed). Only one success is needed to begin the scan, but some likelihood functions have a high fail rate and need this number to be increased (default=20)
        """
            
        #-------------Error handling for arguments----------------------
        outdirlength=len(outdir)    #Multinest has a limit of 100 characters for path+filenames. (note, I hacked it to make this limit 300)
        if outdirlength>100: print >> sys.stderr, "Warning: Output targ\
et path exceeds 100 characters, this may cause problems for some parame\
ter generators or MPI libraries (outdirlength: len({0})={1})".format(outdir,outdirlength)
        print 'Program output to be stored in: {0}'.format(outdir)

        #-------------Set Scan object parameters------------------------
        #Input arguments
        self.outdir = outdir
        self.prior = prior
        self.parorder = parorder
        self.likefunc = likefunc
        self.jobname = jobname
        self.sampler = sampler
        self.sampleroptions = sampleroptions
        self.testing = testing
        self.skipproblems = skipproblems
        
        #Initialise global timing variables
        self.globSTARTtime = time.time()
        self.tmloop = time.time()                                         
        self.tmsamp = time.time()
        self.prevtmsamp = time.time()
        
        #Other initialisation and derived parameters
        #self.rootdir = os.getcwd()                                     #make sure we know what directory we are running in
        self.npars = len(parorder)                                      #number of parameters being scanned (number of dimensions in hypercube)
        self.outputpathbasename = self.outdir+'/'+self.jobname+'-'      #this is sent to the sampler later on and used to name the output files
        self.loop = 0
        self.printing = False
        self.printingmore = False
        self.skipprior = False
        if self.sampler=='list':
            self.skipprior = True                                       #skip scaling in this case (some parameter generators supply the scaled values directly (already in cube))
            self.prior = None if self.skipprior else self.prior         
        self.cubedict = odict()                                         #Must be an ORDERED dictionary!!!
        for param in self.parorder:
            self.cubedict[param] = 0                                    #Initialise order of cubedict to match parorder
            """self.SetupObjects['parorder'] = (for example) ['M0','M12',...]
            self.cubedict = {   'M0'    :1909.59814453,
                                'M12'   :1221.10510254,
                                ...}"""
        self.timingbuffer = []
        self.bufferlength = 1000                                        #output timing info to file every 'bufferlength' iterations.
        retry = False                                                   #rerun the point if an error occurs
        
        if self.testing:
            self.printing = True
            self.retry = False          #do not rerun the point if an error occurs
        
        #Initialize MPI bindings
        self.comm, self.rank, self.size = initMPI() if mpi==None else mpi   #get mpi variables either from user input or the initMPI function.
        
            
        
        # KEY POINT FOR MULTINEST RESUMING!!!
        # ---This (outputpathbasename) is passed to multinest, becomes p_root. 
        # --------It is important for RESUMING jobs!!!-------
        # For a job to resume, this variable must be set to match that of the job to be resumed.
        # One can see how this is formed from the name of the master config module and the
        # jobstamp. Generally the master config module won't have changed (hopefully - an
        # extension could be to extract the archived config files and run those to guarantee
        # compatibility, but currently not doing this) but the jobstamp MAY have. Jobstamp is
        # able to be set by the user, it is part of the CONFIGURATION, so the user has to ensure
        # that their configuration files allow the user the option to fully input the jobstamp
        # (for example many of mine take a name from the user but attach a date, so I need 
        # to modify those config files to allow the USER to enter the desired date). If the
        # jobstamp and masterconfig names match then resuming should work.
         
        maxfilenamelength = len(self.outputpathbasename)+len("post_equal_weights.dat")    
        if maxfilenamelength>100: print >> sys.stderr, "Warning: Output target \
path + longest filename exceeds 100 characters, this may cause problems for some parameter generators or \
MPI libraries (example: len({0})={1})".format(self.outputpathbasename+"post_equal_weights.dat",maxfilenamelength)  
        
        #--------------TEST RUN A POINT---------------------------------
        #Here we run a point through the system so that we can figure
        #out how many slots are required in 'cube'. Might need to change
        #this depending on how errors are handled...
        badpoint = True
        attempts = 0
        print "Test running likelihood function to determine number of \
multinest 'cube' slots needed for output..."
        print "Messages from points:"    
        while badpoint==True:
            cube = np.random.random(self.npars)                         #generate a random hypercube point
            self.cubedict.setvalues(cube)                      
            paramvector = self.cubedict if self.skipprior else self.prior(self.cubedict)
            try:
                lnew, likedict, obsdict, timelist = self.likefunc(paramvector)
                badpoint = False
                print "Good point found!"
            except BadModelPointError as err:
                attempts += 1    
                print 'Attempt {0}: {1}'.format(attempts,err)
                if attempts >= maxtestattempts:
                    print 'Max attempts reached. Please increase max attempts or \
resolve BadModelPointError.'
                    raise                                              
        obslist = [obs for dict in obsdict.values() for obs in dict.keys()]
        likelist = [like for like in likedict.keys()]
        self.cubelength = self.npars + len(obslist + likelist)
        #------------Create info and notes files------------------------
        #Since we have found a valid model point this is a good
        #opportunity to write the job information files.
        if self.rank == 0:                                              #do only if this is the process with ID number 0
            self.writeinfofiles(obsdict,likedict)                       #record the names and columns of the parameters and observables, and additional info about the job.        
            
    def run(self):
        """Begin scan
        Args:
        """
        #--------------RUN SETUP----------------------------------
        
        IAmProcess0 = self.rank==0                                      #check if this is the rank 0 process
        
        """
        if IAmProcess0:    #do only if this is the process with ID number 0
            infoarchive = tarfile.open(outdir+'/'+jobstamp+'.tar','w')
            infoarchive.add(os.path.abspath(inspect.getsourcefile(master))) #gets the path to a source file for a module, converts it to a relative path (from the current directory) and adds the file to the archive.
            for f in master.sourcelist:
                infoarchive.add(os.path.abspath(inspect.getsourcefile(f)))  #imported modules
            for fpath in master.sourcepaths:
                infoarchive.add(os.path.abspath(fpath))     #direct paths to source files
            
            infoarchive.close()
        #Config archiving done
        """
        
        #-------------------------------
        # Run Sampler
        #-------------------------------
        
        #define the sampler wrapper functions:
        
        #------MULTINEST WRAPPER FUNCTION------#
        def multinestrun():
            
            #add internally computed arguments to multinest argument list
            """NOTE: The following keyword arguments are specified internally by pysusy,
            they will just be overwritten if you attempt to set them here, so don't try:
            p_ndims                           #number of dimensions to be scanned (input)
            p_npar                            #tot no. of parameters, should be ndims in most cases but if you need to        
                                              #store some additional parameters with the actual parameters then
                                              #you need to pass them through the likelihood routine
                                              #(things like observables, SUSY spectrum, just extra stuff you want recorded
                                              #in the output chain)
            pyloglike                         #The python likelihood function (input from python)
            pydumper                          #The python 'dumper' function (input from python) (multinest dumps some extra quantities 
                                              #here to help with analysis, doesn't affect scan at all. Can't ignore it though, we
                                              #have to give multinest somewhere to dump this stuff even if we don't use it).
            p_root : "chains/{0}".format(jobname),  #root for saving posterior files (relative to pysusy root directory)
            """
            """OPTIONS SPECIFIED IN PARAMETER GENERATOR SETUP MODULE
            multinest_options = {
            'p_mmodal' : 1,                     #whether to do multimodal sampling
            'p_ceff' : 0,                       #sample with constant efficiency
            'p_nlive' : 1000,                   #max no. of live points
            'p_tol' : 0.5,                      #evidence tolerance factor
            'p_efr' : 0.8,                      #enlargement factor reduction parameter
            'p_ncdims' : 2,                     #no. of parameters to cluster (for mode detection)
            'p_maxmodes' : 10,                  #max modes expected, for memory allocation
            'p_updint' : 100,                   #no. of iterations after which the ouput files should be updated
            'p_nullz' : -1e90,                  #null evidence (set it to very high negative no. if null evidence is unknown)
            'p_seed' : -1,                      #seed for nested sampler, -ve means take it from sys clock
            #bjf> not sure what this is supposed to be > #p_pwrap(4)                       #parameters to wrap around (0 is F & non-zero T)
            'p_feedback' : 0,                   #feedback on the sampling progress?     
            'p_resume' : 1,                     #whether to resume from a previous run
            'p_resume' : 1,                     #whether to resume from a previous run
            'p_outfile' : 1,                       #write output files?
            'p_initmpi' : 0,                    #initialize MPI routines?, relevant only if compiling with MPI
                                               #set it to F if you want your main program to handle MPI initialization
            'p_context' : 0,                    #dummy integer for the C interface (not really sure what this does...)
            }"""
            #note, we are accessing an entry of a dictionary within a dictionary within a module
            mnest_args = self.sampleroptions                            #extract dictionary of multinest arguments
            mnest_args['p_ndims']    = self.npars        
            mnest_args['p_npar']     = self.cubelength
            mnest_args['pyloglike']  = self.mnestLogL
            mnest_args['pydumper']   = self.dumper    
            try:
                mnest_args['p_ncdims']     #see if this entry exists in the dictionary
                if mnest_args['p_ncdims'] > mnest_args['p_ndims']:  #if nCdims > ndims multinest will return an error
                    print('PySUSY Warning for Multinest: nCdims > ndims in Multinest config. Setting nCdims=ndims to resolve.')
                    mnest_args['p_ncdims'] = mnest_args['p_ndims']  #so set nCdims=ndims as a default option
            except KeyError:
                print('PySUSY Warning for Multinest: nCdims not specified in Multinest config. Setting nCdims=ndims to resolve.')
                mnest_args['p_ncdims'] = 2   #If not, give it this default value.
            mnest_args['p_root']     = os.path.abspath(self.outputpathbasename)
            print 'p_root:', mnest_args['p_root']
            print 'p_initmpi:', mnest_args['p_initmpi']
            print '---------------------------------'
            print 'All multinest args:'
            print '---------------------------------'
            for key, val in mnest_args.iteritems():
                print key,": ", val
            print '---------------------------------'    
            
            nestwrapper(**mnest_args)  #unpack keyword arguments from dictionary and use to run multinest!!!
        #------------End Multinest wrapper function---------#
        
        #------------LIST sampling wrapper function------------#
        def listrun():
            #Get the dictionary of options from the parameter generator setup module
            listrun_args = self.sampleroptions                          #extract dictionary of list sampling arguments
            
            #set extra options that should not be screwed with by the user
            listrun_args['ndims']    = self.npars         
            listrun_args['npar']     = self.cubelength
            listrun_args['mpicomm']  = self.comm                        #FOR LIST MODE MPI MUST BE HANDLED FROM PYTHON 
            listrun_args['loglike']  = self.mnestLogL
            listrun_args['root']     = self.outputpathbasename
            listrun_args['parorder'] = self.parorder                    #the order of the parameters is needed because the sampler needs to feed them into cube in the correct order.
            
            listwrapper(**listrun_args)  #unpack keyword arguments from dictionary and use to run sampler!!!
            
        #------------End list sampling wrapper function--------#
        
        #Run the appropriate sampler by choosing the function that runs it from the following dictionary:
        samplers = {'multinest' : multinestrun, #runs Multinest
                    'list' : listrun,           #no sampler, just runs through a supplied list of points
                    }
                    
        #RUN CHOSEN SAMPLER (dig it out of the dictionary of possible samplers and run!)
        print "RUNNING SAMPLER '{0}'".format(self.sampler)
        samplers[self.sampler]()     #Bulk of the code now runs   
        
        self.globENDtime = time.time()
        
        print "Total time taken: {0} seconds".format(self.globENDtime - self.globSTARTtime)
        # DONE!
