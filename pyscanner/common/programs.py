import os
import shutil
import csv
from blockdata import tryfloat
from random import random
from numpy import exp
import subprocess as sp
import platform
import IDpool #to get unique ID number for each process (won't match the multinest MPI ID process numbers)
from extra import BadModelPointError

class Callable:
    """ A tiny wrapper class to let us call a function directly from a class
    without having to make an instance first """
    def __init__(self, anycallable):
        self.__call__ = anycallable

class OutputList(list):
   def __init__(self,l=[],seperator=' ',exclude='',morph=lambda x:x):
      list.__init__(self,l)
      self.seperator=seperator
      self.exclude = exclude
      self.morph = morph
   def __str__(self):
      return self.seperator.join([str(self.morph(i)) for i in self if not hasattr(i,self.exclude)])


class OutputDict(dict):
   def __init__(self,d={},seperator=' ',exclude='',morph=lambda x:x):
      dict.__init__(self,d)
      self.seperator=seperator
      self.exclude = exclude
      self.morph = morph
   def __str__(self):
      return self.seperator.join([str(self.morph(i)) for i in self.values() if not hasattr(i,self.exclude)])

class SUSYFile:
   """File encapsulation for passing data between SUSYPrograms."""
   jobstamp = ''    #Need to run SUSYFile.set_jobstamp to set these before creating SUSYFile instances
   suffix = ''
   #NOTE!! I have set nosuffix=True by default! There are problems with making sure that programs
   #who need specifically names input files have those files named properly, and a mechanism to
   #switch off the addition of a suffix only when copying files for the purpose of input to those
   #programs has not been created. I don't actually need this feature of adding suffixes
   #to files so I am turning it off for now.
   nosuffix = True #Set this to True to prevent the filename from getting a suffix attached during copy
                    #(in case a program requires a specificially named input file)
   mpirank = None   #rank of the mpi process, if mpi initialised through pysusy. If None, set_jobstamp uses the IDpool module to create a pseudo-rank.
   mpisize = None   #number of processes in the mpi process, if mpi initialised through pysusy.
   
   @classmethod
   def set_jobstamp(cls,jobstamp):  #first argument is the class (just as a regular method receives the object name as the first argument)
        """Class function for setting the job ID
        
        Do this before creating any file objects. Need to set the jobstamp
        so that when process IDs are drawn from the ID pool they are all
        drawing from the same pool and don't try to overwrite it with a 
        new pool file.
        
        Also sets the unique file suffix for this process
        
        jobstamp -- unique string to identify this job (must not change between processes,
                i.e. a timestamp is dangerous)
        """
        print 'MPI rank?:', cls.mpirank
        pool = IDpool.getID(jobstamp,verbose=True,MPIrank=cls.mpirank)   #create ID pool object 
        ID = pool.ID
        print 'My ID number is: {0}'.format(ID)
        #SEE NOTE ON SUFFIXES ABOVE!
        #As part of turning off suffixes, I am removing the setting of the
        #parameter entirely, since nosuffix doesn't seem to do much on its
        #own
        #cls.suffix = "-{0}".format(ID)       #define the unique suffix to add to files created through the current process, to prevent file conflicts with other processes
        cls.jobstamp = jobstamp        #store the jobstamp in this class in case we want it later (which we do)
        return pool                    #send back the pool object so that we can access the process ID later on
   #set_jobstamp = Callable(set_jobstamp)

   @staticmethod
   def add_suffix(filename):
       n=filename.rpartition('.')
       return n[0] + SUSYFile.suffix + '.' + n[2]

   def __init__(self,name,outputfrom=None,directory=None):
       """Initialisation for input/output files
       
       Here we set the name of the file object and the programs and directories it
       is associated with. If the file is 'outputfrom' some program it will be assumed
       to be created by that program and thus will not be read in during startup.
       
       Keyword Args:
       
       name         -- the filename
       outputfrom   -- the program object associated with the program which creates this file
       directory    -- the directory the file is located in (assumed to be outputfrom.directory
                       by default)
       """
       #bjf> name of file ('name') needs to be appended with a unique identifier to avoid name clashes when 
       #program is run in parallel on multiple processors. We don't have direct access to the MPI information
       #(since that is handled by Multinest (the parameter generator more generally)), so we have to be a bit
       #less elegant and use the computer name instead of a nice number or something.
       self.name = name
       #bjf> outputfrom used to be either a string or a 'program' object, now it MUST be a program object
       # if file directory is different to program directory this must be supplied in the 'directory' argument as a string
       if outputfrom == None and directory == None:
          raise Exception('Either \'outputfrom\' or \'directory\' must be specified')
       elif directory == None: #i.e. outputfrom != None
          self.directory = outputfrom.directory
          self.outputfrom = outputfrom
       else: #i.e. either (outputfrom and directory != None) or (outputfrom != None and directory == None)
          self.directory = os.path.expanduser(directory) # supports ~ as the home directory
          self.outputfrom = outputfrom #this may be None still
       #bjf> NOTE: I CHANGED THIS TO REQUIRED THE 'directory' ARGUMENT. POSSIBLY NOT ALL SUBCLASSES HAVE BEEN UPDATED ACCORDINGLY

   def copyto(self,path):
      """Copy the file to a different directory."""
      # print 'copying from/to',self.fullpath(), SUSYFile.add_suffix(path)
      if nosuffix:
         shutil.copyfile(self.fullpath(), path)  #do the copying without altering the filename specified
      else:
         shutil.copyfile(self.fullpath(), SUSYFile.add_suffix(path))  #add a suffix to help keep track of what node is doing what

   def extract(self,key):
      """Extract a line of data specified by 'key' as a list.

      Warning: This method is provided only for expediency, it will not work correctly unless the desired line is the only one containing exactly the string given.
      """
      datafile = open(self.directory+self.name, 'rb')
      keylen = len(key)
      for line in datafile:
         if line.find(key)!=-1:
            r = [tryfloat(s) for s in line.split('#',1)[0].split()]
            if len(r) == 1: return r[0]
            return r
      return None

   def strextractall(self):
      """Return a list containing every line of data as a list."""
      data = []
      datafile = open(self.directory+self.name, 'rb')
      reader = csv.reader([s.replace('\t',' ') for s in datafile], delimiter=' ', skipinitialspace=True)
      try: return [line for line in reader]
      except: return None

   def extractall(self):
      return [[tryfloat(s) for s in l] for l in self.strextractall()]

   def fullpath(self):
      return self.directory + SUSYFile.add_suffix(self.name)

   def readdata(self): # TODO: probably a better way to do this
      pass


class DataFile(SUSYFile):
   def __init__(self,name,outputfrom,keys=[]):
      SUSYFile.__init__(self,name,outputfrom)
      self.keys = keys

   def getkeys(self):
      if self.keys==[]: return self.strextractall()[0]
      return self.keys

   def __str__(self):
      data = self.strextractall()
      lines = []

      if self.keys==[]:
         l = len(data[0])
         if data!=None: lines=[' '.join(l) for l in data[0:]]
      else:
         if data!=None: lines=[' '.join(l) for l in data]
         l = len(self.keys)

      if lines==[]: return ' '.join([str(None) for i in range(l)])
      return ' '.join(lines)



class SUSYProgram:
   """Callable wrapper for a program to calculate observables."""

   def __init__(self,executable,directory,inputs=[],outputs=[],inputsdir="",outputsdir="",commandformat="%(inputfiles)s %(outputfiles)s",checks=[]):
      self.executable = executable
      self.directory = os.path.expanduser(directory) # supports ~ as the home directory
      self.outputfiles = OutputList(outputs,morph=lambda x:SUSYFile.add_suffix(x.name))
      self.inputfiles = OutputList(inputs,morph=lambda x:SUSYFile.add_suffix(x[0])) # list of pairs mapping input filenames to input files
      self.inputsdir = inputsdir
      self.outputsdir = outputsdir
      self.commandformat = []
      self.runfirst = False #bjf> BRUTALLY HACKED IN FLAG TO LET ME CHOOSE WHICH PROGRAM RUNS FIRST MANUALLY
      self.pipein,self.pipeout = None, None
      self.checks = checks #should be a list of dictionaries defining the entries of the output files that should be checked (see comments in __call__ below for example)
      self.verbose = False #set this to true to always output program stdout to stdout, regardless of other instructions
      # all this to handle piping to/from programs
      i = iter(commandformat.split())
      for s in i:
         if s == '<': self.pipein = i.next()
         elif s == '>': self.pipeout = i.next()
         else: self.commandformat+=[s]
      self.commandformat = ' '.join(self.commandformat)
      #print 'command:',self.commandformat

   def __call__(self,verbose=True):
      """Run the program."""
      import time #timing debug stuff
      # First, ensure all prerequisites are present
      if self.verbose:
            verbose=True    #if program has verbose property explicitly set to True valued, ignore generic verbosity instructions.
            
      for key,f in self.inputfiles:
         f.copyto(self.directory+self.inputsdir+key)
      os.chdir(self.directory)
      # set up any required piping
      pipein = open(self.pipein % self.__dict__,'r') if self.pipein else None
      pipeout = open(self.pipeout % self.__dict__,'w') if self.pipeout else open("/dev/null",'w') if not verbose else None
      #Opens a file if one is specified in the program command format, if none specified check to see if 
      #the user has instructed program output to be supressed (verbose=False) if not then inherits the stdout
      #for this process from the parent process.
      #print 'calling',self.commandformat % self.__dict__ #bjf
      #print self.executable  
      #print self.directory
      #print pipein 
      #print self.pipein % self.__dict__
      
      t1 = time.time()
      if verbose: print 'Running: {0}'.format(self.executable)
      if verbose: print [self.executable]+((self.commandformat % self.__dict__).split()), pipein, pipeout
      sp.call([self.executable]+((self.commandformat % self.__dict__).split()),stdin=pipein,stdout=pipeout,stderr=sp.STDOUT)
      t2 = time.time()    
      # print 'system call',' : ',(t2-t1)*1000.0
      
      if pipein: pipein.close()
      if pipeout: pipeout.close()
      for f in self.outputfiles:
         #print 'reading in', f, '...'
         f.readdata() # ensure the data in SLHAFiles is kept up to date.
         
      #print "f.block('ALPHA')", f.block('ALPHA')

      #=================================================
      # OUTPUT CHECKS -NEW!! (1 Aug 2011)
      #=================================================
      # We have just called readdata on the output files so we should now be able to perform checks
      # on the output to decide if we should bother continuing execution of the loop. If this is a bad
      # model point we want to raise the error BadModelPointError and skip the rest of the loop.
      #
      # I am making a new parameter for this class, which is a function to call to check the output for
      # errors. This is optional for backwards compatibility. If supplied during creation of the 
      # SUSYProgram objects it is run now.
      
      # EXAMPLE TEST DEFINITIONS
      #check1={
      #  'filename': 'SSoutput.dat',
      #  'block':    'SPINFO',
      #  'index':    3,
      #  'checktype': 'existbad',
      #       }
      #check2={
      #  'filename': 'SSoutput.dat',
      #  'block':    'SPINFO',
      #  'index':    4,
      #  'checktype': 'notval',
      #  'checkval': 0 
      #       }
      #checks=[check1,check2]
      #verbose=True  #temporary
      for f in self.outputfiles:
          for check in self.checks:   #cycle through list of checks to complete
            try:
               filename=check['filename']
               block=check['block']
               index=check['index']
               checktype=check['checktype']
            except KeyError:
               raise KeyError('Error, output file check definition missing entry or possesses invalid entry')
            if f.name==filename:
               try:
                  if verbose: print 'Checking output file entry: Block {0}, index {1}'.format(block,index)
                  val=f.block(block)[index].value  #try to extract current value of this file entry
                  if checktype=='existbad':
                     msg='Bad Model Point in file check! filename:{0}, block:{1}, index:{2}, value:{3}'.format(filename,block,index,val)
                     if verbose: print msg
                     raise BadModelPointError(msg)     #if checkval='existbad' the existence of this entry is taken to mean there is a problem with the output and we should skip this model point
                  try:
                     if checktype=='val':
                        #in this case raise error if item has the specified value
                        if check['checkval']==val:
                           msg='Bad Model Point in file check! filename:{0}, block:{1}, index:{2}, value:{3}'.format(filename,block,index,val)
                           if verbose: print msg
                           raise BadModelPointError(msg)
                     if checktype=='notval':
                     #in this case raise error if item has the specified value
                        notval=check['checkval']
                        if notval!=val:
                           msg='Bad Model Point in file check! filename:{0}, block:{1}, index:{2}, value:{3}!={4}'.format(filename,block,index,val,notval)
                           if verbose: print msg
                           raise BadModelPointError(msg)
                  except KeyError:
                     msg="if a program output check dictionary has checktype=='val' or 'notval' \
it must also be given an item 'checkval' to compare the item value to."
                     print "ERROR(KeyError): Invalid file check defined for file {0}, block {1}, index {2}, \
checktype {3}".format(filename,block,index)
                     raise Exception(msg) #don't raise a KeyError or it will get handled wrong and turned into
                                          #a BadModelPointError. Want to kill the code instead.
               except (TypeError, KeyError):
                  if checktype=='existgood':
                     msg='Bad Model Point in file check! Entry filename:{0}, block:{1}, index:{2} does not exist'.format(filename,block,index)
                     if verbose: print msg
                     raise BadModelPointError(msg)
                  if checktype=='val' or checktype=='notval':
                     msg="Invalid file check defined for file {0}, block {1}, index {2}, \
checktype {3}. If a program output check dictionary has checktype=='val' or 'notval' the file entry must \
always exist (was not found to exist now)".format(filename,block,index,checktype)
                     raise KeyError(msg)
                  #else continue on, this means everything is fine.
      if verbose: print 'file checks passed'
      #==========End output checks==============================

   def getoutput(self,name):
      for f in self.outputfiles:
         r = f.extract(name)
         if r: return r
      return None

   def allfiles(self):
      return [n[0] for n in self.inputfiles] + [f.name for f in self.outputfiles]

   def addofiles(self,*filenames):
      """Adds a SUSYFile from a filename. (To add an SLHAFile append to outputfiles manually.)"""
      files = []
      for n in filenames:
         f = SUSYFile(n,self)
         files.append(f)
      self.outputfiles += files
      return files

   def addifiles(self,*files):
      for f in files:
         if isinstance(f,tuple): self.inputfiles.append((f[0],f[1]))
         else: self.inputfiles.append((f.name,f))



class Parameter:
   def __init__(self,*args,**kwargs):
      """"""
      #bjf> removed this stuff since the priors and ranges are now taken care of elsewhere
      #if 'likefunc' in kwargs:
      #   likefunc = kwargs['likefunc']
      #else:
      #   likefunc = pymc.uniform_like
      #   self.initial = (args[0]+args[1])/2
      if 'block' in kwargs:
          if 'index' in kwargs:
              self.block = kwargs['block']
              self.index = kwargs['index']
          else:
              print('Parameter is missing \'index\' argument')
              exit(1)   #Exit due to missing input    
      
      if 'proposal' in kwargs:
         proposal = kwargs['proposal']
      else:
         proposal = lambda x: x

      if kwargs.has_key('fixedargs'): args = kwargs['fixedargs']
      if kwargs.has_key('initialval'): self.initial = kwargs['initialval']
      #bjf> removed this stuff since the priors and ranges are taken care of elsewhere
      #self.likefunc = lambda *x: likefunc(*(x+args))   
      #self.proposal = lambda x: proposal(args[0]) if x<args[0] else proposal(args[1]) if x>args[1] else proposal(x) 
      self.value = None
      self.args = args

   def __str__(self):
      return str(self.value)
    
    #bjf> removed for now since priors and ranges taken care of elsewhere, and points generated by multinest
    #may need this stuff again if we reimplement the MCMC scan option.
   """def setRandom(self):
      mx = -1000000
      for n in range(1000):
         x = (self.args[1]-self.args[0])*random() + self.args[0]
         if self.likefunc(x) > mx: mx = self.likefunc(x)

      while True:
         x = (self.args[1]-self.args[0])*random() + self.args[0]
         r = random()
         if exp(self.likefunc(x)-mx) > r:#random():
            self.initial = x
            return
    """
