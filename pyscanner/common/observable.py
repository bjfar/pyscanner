print 'subcheckpoint'
import programs
print 'subcheckpoint2'
import pymc
print 'subcheckpoint3'
import sys
print 'subcheckpoint4'
import time
print 'subcheckpoint5'
from scipy import exp, sqrt
print 'subcheckpoint6'
from numpy import abs
print 'subcheckpoint7'
from extra import BadModelPointError
from common.programs import OutputList

class Observable:
   def __init__(self,slhafile=None,block='',index=0,average=0,sigma=0,likefunc=pymc.normal_like,printing=True,positivedefinite=False,uselike=True,**kwargs): # TODO: this messes things up if printing is false
      r"""An observable quantity including a calculated value and an experimental mean and deviation.

      Usage
      -----
      Observable() can be called two ways, by providing either the name of the result and the program used to calculate it,
      or the explicit file, block name, and index of the result. The experimental average and standard deviation must also be provided,
      along with an (optional) likelihood function (defaulting to a normal distribution).

      first method
         *newobservable* = Observable(*result name*, *result calculator*, *experimental average*, *standard deviation*, likefunc=*likelihood function*)
      second method
         *newobservable* = Observable(slhafile=*SLHAFile*, block=*block name*, index=*index*, average=*experimental average*, *standard deviation*)

      Parameters
      ----------
      :name: A unique string used to identify the observable (in SLHA format the item comment is used).
      :calculator: A callable (probably SUSYProgram) to calculate a result, defining a member function getoutput().
      :average: The experimental average.
      :sigma: The experimental standard deviation.
      :likefunc:
         The function to calculate the likelihood from *calculator*, *average* and *sigma* (default is a normal distribution),
         must take 3 arguments: the calculated value, experimental mean and sigma (or similar).
      :slhafile: The SLHAFile containing the required result.
      :block: The name of the block in slhafile which contains the required result.
      :index: The index of the required result in the block specified.
      :printing: Whether or not the value of this observable is included in the printout.
      :positivedefinite: If True then .results() will return the absolute value of the number found in the specified block file
      :theoryupper: (bjf> index of this thing?)
         Standard deviation of the theoretical uncertainty. This is convolved with the experimental sigma for the final sigma.
         This may be a callable if the theoretical uncertainty is dynamic.
      :theorylower:
      :theorysigma: name or index in *block* of calculated theoretical standard deviation. Calculated from theoryupper and theorylower if not specified.
      :uselike: Default TRUE. If set to false, the likelihood value for this observable will be computed, but not incorporated
      into the total likelihood used to guide the scan. For likelihood data one wishes to fold in post-scan.
      """
      if slhafile:
         self.slhafile = slhafile
         self.block = block.upper() #bjf> making block names uppercase, because I have changed the matchmaker routines to convert all strings to uppercase. This should remove case-sensitivity.
         self.index = index
      self.average = average
      self.sigma = sigma
      self.likefunc = likefunc
      self.value = None
      self.theorybounds = 1
      self.positivedefinite = positivedefinite #<bjf
      self.uselike = uselike #<bjf
      if not printing: self.noprint = True # TODO: the value of this doesn't have an effect, only the existence of the member 'noprint'. Maybe bad
      for key,arg in kwargs.items():
         if key in ['theorysigma','theoryupper','theorylower','theorybounds']:
            self.__dict__[key] = arg

   def getItem(self,index=-1):
      #if index==-1 and isinstance(self.index, list): # if self.index is a list then return a vector of the values of the given indices
         #return [self.getItem(i) for i in self.index]
      #bjf>
      #if self.index == 0:
         #print 'in getItem'
         #print self.block
         #print self.index
         #print self.value
         #print self.slhafile.block(self.block,self.index)
      if self.index == 'noindex': #certain softsusy blocks have no index, need to make sure the observables for these are defined with index='noindex'
         #print 'in getItem'
         #print self.block
         #print self.index
         #print self.__dict__
         #print self.value
         #print self.slhafile.block(self.block,'blockvalue')
         #raise Exception
         val=self.slhafile.block(self.block,'noindex')   #items stored under dictionary name 'noindex' if the block has no index
         return val
      if self.index == "blockvalue":  #Some blocks have values associated with them. To extract this as an observable the Observable object must be defined with index="block"
         val=self.slhafile.block(self.block,'blockvalue') #items stored under dictionary name 'blockvalue' if it is from the line with the block name.
         return val
      #<bjf else do the original thing...
      return self.slhafile.block(self.block,self.index if index == -1 else index)

   def results(self):
      """Return the calculated value."""
      if self.positivedefinite:
         try:
            self.value = abs(self.getItem())   #bjf> if this quantity is supposed to be positive, we return the absolute value of whatever is in the SLHA file (SoftSusy gives me back some sparticle masses as negative, this is my way around that)
         except TypeError:      #if no value recorded due to failed model point, will get a TypeError (abs() cannot accept NoneType objects), need to handle this.
            self.value = self.getItem()
      else:
         self.value = self.getItem()
      return self.value

   def sigma2(self):
      theorysigma = 0
      if hasattr(self,'theorysigma'):
         theorysigma = self.getItem(self.theorysigma)
      elif hasattr(self,'theoryupper'): #bjf> this is some thing Daniel used with NMSSMtools
         theorysigma = (self.getItem(self.theoryupper) - self.getItem()) / self.theorybounds # TODO: think about theory lower bounds, important?
         #bjf> what is theorybounds??? This equation makes no sense.
      return self.sigma**2 + theorysigma**2 #if no theorysigma stuff provided, just squares the experimental sigma.

   def likelihood(self):
      return self.likefunc(self.results(),self.average,sqrt(self.sigma2()))
      # bjf> this was hiding syntax errors in my custom likelihood definitions, I am removing it so these show up.
      # I hope it isn't really necessary, should catch problems other ways.
      #try: return self.likefunc(self.results(),self.average,sqrt(self.sigma2()))
      #except TypeError: return 0.0

   def __str__(self):
      return str(self.value)

   def label(self,name=''):
      return name

class VectorObservable(Observable):
   def __init__(self,slhafile=None,block='',*indices,**kwargs):    
      Observable.__init__(self,slhafile,block,average=0,sigma=1.0,likefunc=None,printing=True,**kwargs)
      self.indices = indices

   def likelihood(self):
      return 0.0

   #bjf> Daniel's function didn't seem to work right, so I wrote a new one. No recursive behaviour so
   #only works for two index observables
   #def getItem(self, index=None):
      #if index:
         #item = self.slhafile.block(self.block)
         #print item
         #print item[index[0]]
         #print item[index[0]][index[1]]
         #print item[index[0]][index[1]].value
         #return item[index[0]][index[1]].value
      #return programs.OutputList([self.getItem(i) for i in self.indices])
      
   def getItem(self, index=None):
      if index:
         item = self.slhafile.block(self.block)
         try:
            for i in index:
               item = item[i]
         except TypeError:
            if item: item = item[index]
            else: return None
         except AttributeError:
            print "Error extracting value from file {0}, block {1}, index {2}. Blueprint may \
be missing, perhaps because file object is created from a class lacking this blueprint, for \
example from 'SLHAFile' rather than 'SpectrumFile'.".format(self.slhafile.name,self.block,index)
            raise
         return item.value
      return programs.OutputList([self.getItem(i) for i in self.indices])

   def label(self,name=''):
      #print '\nlabelling...',' '.join(name+str(i) for i in range(len(self.indices))) TODO: remove
      return ' '.join(name+str(i) for i in range(len(self.indices)))

class NamedObservable(Observable):
   def __init__(self,name='',calculator=None,average=0,sigma=0,likefunc=pymc.normal_like,printing=True,**kwargs):
      Observable.__init__(self,average=average,sigma=sigma,likefunc=likefunc,printing=printing,**kwargs)
      self.name = name
      self.calculator = calculator

   def getItem(self,name=''):
      return self.calculator.getoutput(self.name if name=='' else name)

class CompositeObservable(Observable):
   """This observable takes as arguments several other variables and combines them according to
   a user-supplied function"""
   def __init__(self,function,observables,average=0,sigma=0,likefunc=pymc.normal_like,printing=True,**kwargs):
      Observable.__init__(self,average=average,sigma=sigma,likefunc=likefunc,printing=printing,**kwargs)
      self.function=function        #the function into which observables are to be fed and a value for the composite observable extracted
      self.observables=observables  #the list of observables objects out of which the composite observable is to be built
      
   def getItem(self):
      vals = [obs.results() for obs in observables] #compute the values for the consituent observables
      return self.function(*vals)   #feed vals into the combination function and return the result
      
#WARNING!!! THIS IS EXPERIMENTAL. I need an object that handles multiple indices, but still acts like a normal
#observable. I have cannibalised this from VectorObservable, hope it works. It will accept many more layers
#of indices than it should, so be careful using it.
class MultiIndexObservable(Observable):
   def __init__(self,slhafile,block,indices,**kwargs):
      Observable.__init__(self,slhafile,block,**kwargs)
      self.indices = indices

   def getItem(self, index=None):
      if index:
         item = self.slhafile.block(self.block)
         try:
            for i in index:
               item = item[i]
         except TypeError:
            if item: item = item[index]
            else: return None
         except AttributeError:
	    print "Error extracting value from file {0}, block {1}, index {2}. Blueprint may \
be missing, perhaps because file object is created from a class lacking this blueprint, for \
example from 'SLHAFile' rather than 'SpectrumFile'.".format(self.slhafile.name,self.block,index)
	    raise
         return item.value
      #print 'self.indices', self.indices
      #print 'self.getItem(self.indices)', self.getItem(self.indices)
      #self.indices should just be a single list, so we should be able to retrieve the value of the observable
      #by calling getItem with the index list as the argument
      return self.getItem(self.indices)
      
      
   def label(self,name=''):
      #print '\nlabelling...',' '.join(name+str(i) for i in range(len(self.indices))) TODO: remove
      return ' '.join(name+str(i) for i in range(len(self.indices)))

class SimpleObservable: #TODO: this needs a rethink
   def __init__(self,keys,getoutput=None):
      self.keys = keys
      if not getoutput: getoutput = lambda: self.value
      self.getoutput = getoutput
      self.value = None
   def getkeys(self):
      return self.keys
   def __str__(self):
      self.value = self.getoutput()
      if hasattr(self.value,'__iter__'): return ' '.join([str(x) for x in self.value])
      return str(self.value)
   def label(self,name=''):
      if not self.keys: return name
      if hasattr(self.keys,'__iter__'): return ' '.join([str(x) for x in self.keys])
      return self.keys


class Simulator:
   """Wrapper for programs."""
   def __init__(self,inputdict):   #bjf> now requires a dictionary of objects (programs, observables etc)
      self.parameters = programs.OutputDict(exclude='noprint')
      self.observables = programs.OutputDict(exclude='noprint')#,morph = lambda x: x.value)
      self.moreoutput = programs.OutputList(exclude='noprint')
      self.delayedoutput = programs.OutputList(exclude='noprint')
      self.programs = {}
      self.timingbuffer = []    #list to store timing information in so we don't have to write to file every iteration
      self.bufferlength = 100    #length of timing buffer
      for n,p in inputdict.iteritems(): # TODO: using isinstance() is not really extensible (n are the keys, p the values of the entries in the dict)
            #takes the input dictionary and seperates it into several dictionaries containing the different tpyes of objects.
         if isinstance(p,programs.SUSYProgram): self.programs[n]=p
         if isinstance(p,Observable): self.observables[n]=p
         if isinstance(p,programs.Parameter): self.parameters[n]=p
         if isinstance(p,programs.DataFile): self.moreoutput.append(p)
      
      print 'Initialising Simulator:'
      print 'Loading SUSYPrograms objects...'
      print self.programs.keys()   
      print 'Loading Observables objects...'
      print self.observables.keys()   
      print 'Loading Parameter objects...'
      print self.parameters.keys()
      print 'Loading DataFile objects...'
      print self.moreoutput
            
      try:
         self.transformation = inputdict['Transformation']  #see if a coordinate transformation has been defined
         print 'Loading coordinate transformations...'
      except KeyError:
         self.transformation = lambda x: x  #if no transformation is provided, assume identity transformation
      
      #bjf> added these properties because multinest needs them
      self.ndims = len(inputdict['parorder'])   #not using len(self.parameters) anymore as there may be a transformation which is one-to-many (i.e. defines more Parameters to go in the input files than are actually scanned)
      self.nobs = len(self.observables) #just the number of observables defined by the user
      #If some observables are 'VectorObservable's then these take up multiple output 
      #slots, so we need to compute how many extra slots we need to allow for this.
      self.nextra = 0
      for obs in self.observables.values():
         if isinstance(obs,VectorObservable):
            self.nextra += len(obs.indices)-1 #minus one because there is already one slot assigned for this observable
      self.nINpars = len(self.parameters)   #store this as well since we may want to store the INpars in the output.
      #<bjf
      
      self.execorder = self.dumbsort(self.programs.values())
      self.inputfiles = sum([[f[1] for f in p.inputfiles if f[1].outputfrom == None] for p in self.programs.values()],[])
      self.laststring = ''
      #bjf> removed since parameters generated by multinest. May need this again if reimplementing MCMC.
      #for p in self.parameters.values(): p.setRandom()
   
   def checkobs(self,program,verbose=True):
      if verbose: print "checking file output..."
      #checks that the output files from program 'program' have entries corresponding to the observables defined in the observables list
      for name, obs in self.observables.iteritems():
         for f in program.outputfiles:
            try:
               if obs.slhafile==f: #if this observable is associated with one of the output files produced by this program...
                  val=obs.getItem()	#use getItem because .results() has not been run yet, so .value attribute of observables has not yet been set.
                  #verbose=True
                  if verbose: print 'checkobs val:', name, val
                  #val=f.block(obs.block)[obs.index].value  #try to extract current value of this file entry
                  #except (KeyError, TypeError):
		  #ensure observable has been given a numerical value or a list (should check list for numerical values too but haven't bothered)
                  if type(val)!=float and type(val)!=int and type(val)!=OutputList:
                     if val==None:
                        msg='Bad Model Point in output observable check! Required observable \
#{0} from filename:{1}, block:{2}, index:{3} returned as None'.format(name,f.name,obs.block,obs.index)
                        if verbose: print msg
                        raise BadModelPointError(msg)
                     msg='Invalid observable type detected! Please check program output and observables definitions.'
                     print 'checkobs val returned:', name,' value:', val
                     print 'type:', type(val)
                     raise TypeError(msg)
            except AttributeError:
               pass  #if the observable has no slhafile attribute then we don't need to check it, go to the next one. 
               
   def calculateall(self,inputpars=[],verbose=True,checkoutput=True): #TODO: need to come up with a reasonable way to store results
      import time #timing debug stuff
      if isinstance(inputpars,dict): inputs = [i for i in inputpars.items() if i[0] in self.parameters.keys()]
      else: inputs = [(n,p) for n,p in zip(self.parameters.keys(),inputpars)]
      for f in self.inputfiles: f.readdata() # TODO: replace with update()
      for key,val in inputs:
         self.parameters[key].value = val   #bjf> is this redundant?
         block = self.parameters[key].block #get the SLHA block and index for this parameter
         index = self.parameters[key].index
         for f in self.inputfiles: 
            try:    #adding some exception handling because it is easy to screw up the config so that pysusy tries to access invalid SLHA entries
                f.block(block)[index].value = val #TODO: does this need to deal with SUSYFiles as well as SLHAFiles? May need to generalise a bit
            except (KeyError, TypeError):
                print 'Key or Type error - may be trying to access non-existent SLHA entry or file'
                print 'dumping current variables:'
                print 'file = ', f.name
                print 'block = ', block
                print 'index = ', index
                print 'value = ', val
                raise   #re-raise the exception so the program stops and we get the traceback
      timelist=[]   #list to record execute times of program
      for program in self.execorder:
         t1 = time.time() 
         if verbose: print 'run program'
         program(verbose)   #if verbose=False then program stdout is dumped to dev/null (oblivion) unless it is piped to a useful output file.
         #program(True)
         if verbose: print 'end program'
         t2 = time.time()    
         runtime=(t2-t1)*1000.0
         if verbose: print 'Program ',program.executable,', runtime',' : ',runtime
         timelist+=[runtime]
         if verbose: print 'checkoutput', checkoutput
         if checkoutput:    #make sure all the observables defined by the user to be extracted from this program's output have entries in the output file
             self.checkobs(program,verbose)
      return timelist
    
   def outputlist(self):
      return [(o.results(),o.average,o.sigma) for o in self.observables.values()]

   def dumbsort(self,plist): # TODO: should really just replace the program list with some sort of tree structure
      temp = list(plist)
      final = []
      for p in temp: p.oflag = False

      while len(temp) > 0:
         for p in temp:
            for f in [t[1] for t in p.inputfiles]:
               if f.outputfrom != None: f.outputfrom.oflag = True
         temp2 = [p for p in temp if p.oflag == False]
         temp = [p for p in temp if p.oflag == True]
         for p in final:
            for f in [t[1] for t in p.inputfiles]:
               if f.outputfrom != None: f.outputfrom.oflag = False
         final += temp2
      final.reverse()
      for p in plist: del p.oflag
      #bjf> BRUTAL HACK TO ENSURE A PROGRAM WITH .runfirst ATTRIBUTE SET TO 'TRUE' WILL RUN FIRST
      final = [p for p in final if p.runfirst==True] + [p for p in final if p.runfirst==False]
      #print [p.executable for p in final]
      #quit()
      return final

   def recordresults(self,f):
      self.laststring = ' '.join(self.parameters.keys())+' '+' '.join(o.label(n) for n,o in self.observables.items())+' '+' '.join(o.label() for o in self.moreoutput)+' '+' '.join(o.label() for o in self.delayedoutput)+'\n'
      self.recordresults = self._recordresults # I don't know if doing this is actually a good idea. Interesting though
      self.recordresults(f)

   def _recordresults(self,f):
      """Record all the output from the simulations to a given file (which should be in append mode)."""
      if len(self.delayedoutput)> 0: self.laststring+=' '+str(self.delayedoutput)
      f.write(self.laststring+'\n') # adding delayedoutput here allows it to be evaluated after the loop
      self.laststring = str(self.parameters) + ' '+str(self.observables) +' '+str(self.moreoutput)
   
   def transform(self,point):
       """Take the dictionary 'point', which contains input parameters and values from the parameter generator,
       and map the values to a dictionary with names matching the Parameter objects which will be used to put the
       values in the first input file. This extra step allows us to perform a coordinate transformation on the
       parameters from the parameter generator, so they don't have to match those required by the first input file"""
       
       transformedpoint = self.transformation(point)    #transformation is a function which takes one dictionary and returns a new one
       return transformedpoint
       
   def runpoint(self,point,printing=False,skipproblems=False,retry=True): # TODO: use this in susymodel.py
      #if skipproblems == true, we skip over this point in the event of an error
      #if retry == true, we give the point 3 chances to not return an error, then we skip it (no effect if skipproblems==false)
      attempts=1
      logp, likes = -1, -1 #default values. These should only be returned if problems are encountered.
      timelist=[-1]   #if point encounters an error this value will persist into the timing output file
      while True: #bjf> encountering some errors occasionally, trying to bypass them with some exception handling
         if retry: 
            chances=3
         else:
            chances=1
         if attempts<=chances: #let the code have 'chances' tries to do the calculation.
            try:
               if isinstance(point,str): point = [programs.tryfloat(p) for p in point.split()]
               #Transform the input scan parameters to the Les Houches (or otherwise) required form using user defined function
               transformedpoint = self.transform(point)
               timelist=self.calculateall(transformedpoint,printing) #timelist is a list of the execution times of the sub-programs, in the order they were run.
               if printing: print ', '.join([x+':'+str(y.value) for x,y in self.parameters.items()])
               if printing:
                  print "List of observables computed:"
                  print "*************************"
                  for key,val in self.observables.items():
                     print "Observable:",key," Value: ",val.results()," Log Likelihood: ", val.likelihood(), "val.average",val.average,"val.sigma",val.sigma
                  print "*************************"
               #print 'loop'
               #for key,val in self.observables.items():
               #   if key=='alpha' or key=='tanbeta':
               #      print "Observable:",key," Value: ",val.results()," Log Likelihood: ", val.likelihood(), "val.average",val.average,"val.sigma",val.sigma
               #names = [key for key,val in self.observables.items()]
               likes = [(o.likelihood(), o.uselike) for o in self.observables.values()] #compute likelihood values and whether or not they are to be used to guide the scan
               if printing: print '(Likelihood value,uselike):', likes
               #print names
               #print likes
               #print zip(names,likes)
               truelikes = [like[0] for like in likes if like[1]==True] #compiles a list of the likelihood values from observables with uselike==True 
               alllikes =  [like[0] for like in likes] #all the likelihood values computed
               if printing: print 'Number of likelihood values in use:  ', len(truelikes)
               if printing: print 'Number of likelihood values in total:', len(alllikes)
               logp = sum(truelikes)
               if printing: print '-2 Log Likelihood (chi^2)', -2*logp
               break #if everything successful leave the loop
            except IOError, msg:
               print 'IOError encountered; Possible reasons:'
               print '1. Environment variable TMPDIR specifies relative rather than absolute \
path. Absolute path to temporary directory must be used.'
               raise
            except BadModelPointError as e:   #this exception should be raised under any conditions that indicate a bad model point has been encountered (IOErrors etc due to sub codes not producing proper output))
               #print 'BAD POINT'
               timelist += [e.msg]
               if skipproblems: #set skipproblems to True if you want to skip any random errors that turn up and hope
               #they are a problem with a particular point, not the code. Set to False during testing to find problems. NOTE: These errors are not so random anymore, only BadModelPointErrors are handled.
                  if printing: print >> sys.stderr, "Error encountered while running observable.runpoint; retrying point...(attempt {0})\n".format(attempts)
                  if printing: print >> sys.stderr, sys.exc_info(), "\n"
                  if retry: time.sleep(3)    #wait some time and hope problem fixes itself
                  attempts+=1 #add 1 to list
               else:
                  raise
         else:
            if printing: print >> sys.stderr, "WARNING: Error in point could not be resolved, skipping point...(message below). Problems may exist in the programs being run or the configuration files.\n"
            if printing: print >> sys.stderr, sys.exc_info(), "\n"
            alllikes = [-1e300 for o in self.observables.values()] #set all likelihoods of observables to 'minimum' value.
            logp = sum(alllikes)  
            break #leave the loop
      if timelist==[-1]: 
         print 'Unexplained error in program evaluation loop encountered, exiting pysusy to allow evaluation of current output state...'
         quit() #want to check why this is   
      return logp, alllikes, timelist
