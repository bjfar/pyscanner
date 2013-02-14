"""Reading and writing routines for a generic 'block' file format.


"""

import re
from extra import BadModelPointError

def tryfloat(s):
   if s == None or s == 'None': return None
   try:
      s2=s.replace("D","e")
      ret = float(s2)
   except ValueError:
      ret = s
   return ret

def fortfloat(s):
   if s == None: return None
   return float(s.replace('D','e'))

class FileIterator:
   """Simple wrapper for an iterator (over a file or a list) supporting the iterator commands curr() and prev().

   Not really suitable for large files.
   """
   def __init__(self,filename="",pars="rb",lines=[]):
      try:
         if filename: self.lines = open(filename,pars).readlines()
         elif lines: self.lines = lines
         self.current = -1
      except IOError as e:
          #Assume the lack of an input file indicates that this is a bad model point
          raise BadModelPointError("IOError caught: File {0} not found".format(filename))
          
   def __iter__(self): return self
   def next(self):
      if self.current < len(self.lines)-1:
         self.current += 1
         return self.lines[self.current]
      self.current=0
      raise StopIteration
   def prev(self):
      if self.current > 0:
         self.current -= 1
         return self.lines[self.current]
      return self.lines[0]
   def curr(self):
      try:
         return self.lines[self.current]
      except IndexError:
         return None

class Blueprint:
   """Definition of a block or item."""

   def __init__(self,makeclass,format,subblueprints=[]):
      """Initialise the blueprint.

      The formatting string is as defined for the %-operator (similar to the c-style scanf/printf string). For example, applying the formatting string 'BLOCK %(name)s' to input 'BLOCK blockname' will match the literal substring 'BLOCK', then create a member item.name for the item and assign to it the value 'blockname'.

      Parameters:
         format: string defining the format to match for this blueprint
         makeclass: the class to create assuming a match
      """
      self.format = format
      self.matchmaker(format)
      self.makeclass = makeclass
      self.subblueprints = list(subblueprints)

   def construct(self,fileiter):
      """Create and return a block or item matching a given signature (return None if no match)."""
      d = self.match(fileiter.curr())	#d is the dictionary containing items matched from the current line of the file (according to Blueprint)
      if d == None: return None, False
      c = self.makeclass(self)
      c.__dict__.update(d)  #this takes the items in dictionary d and adds them to the dictionary of the Instance of the new Block or Item.
                            #Note: The elements of this dictionary are interpreted as the **attributes** of the instance.
      # bjf> SPECIAL EDIT. Some Blocks have blueprints with entries like 'value'. We need a way for
      # these values to be placed into a special indexless "Item" of the Block, so that they can be extracted in the
      # normal way by an Observable
      #print c.__class__
      #print c.__dict__
      #print dir(c)
      try:
         if c.__class__==Block: #make sure we only try this for Blocks, not for Items.
            #print c.__class__
            #print c.__dict__
            #print dir(c)
            #append the special Item to the Block. I will try making a new Item which just steals the dictionary
            #(currently containing no Items) from the Block. It will have the Block's Blueprint, but that should
            #be ok I think.
            blockitem = Item(self)
            d['index']='blockvalue'	#set a special index which can be used to retrieve this item from the Block.
            blockitem.__dict__.update(d)
            blockitem.blueprint='noblueprint'	#kill the blueprint, it will be used to create a new line in the SLHA file (don't want this,
                                                #already created by Block blueprint).
            #print blockitem.__class__
            #print blockitem.__dict__
            #print blockitem.index
            #print dir(blockitem)
            c.append(blockitem)
      except KeyError:
         pass
      try:
         fileiter.next()
      except StopIteration:
         return c, True
      end = False
      while end == False:
         tempc = None
         for blueprint in self.subblueprints:
            tempc,end = blueprint.construct(fileiter)
            if tempc:
               c.append(tempc)
               break
         if tempc == None:  # if it can't read a particular line, then it returns control to the blueprint one level up
            return c, False
      return c, True

   def writeout(self,block,ffloat=False):
      """Write the block to a string."""
      s = self.format % block.__dict__
      if ffloat:
         s = list(s)
         try: # TODO: bad hack
            pos = s.index('e')
            while pos != -1:
               if s[pos+1] in ['+','-'] and s[pos-1] in [str(i) for i in range(10)]: s[pos] = 'D'
               pos = s.index('e',pos+1)
         except ValueError: pass
         except IndexError: pass
         s = ''.join(s)
      return s

   def match(self,string):
      #if self.makeclass==Block:
      #    print self, string
      return self._match(self,string)

   def matchmaker(self,formatstring):
      """Write a function that parses a single line of data."""
      conversions = {'d':'int','e':'fortfloat'}
      words = formatstring.split()
      fstring =  'def func(self,string):\n'
      fstring += '\ti = iter(string.split())\n'
      fstring += '\td = {}\n'
      fstring += '\tdone = False\n'
      fstring += '\ttry:\n'

      for w in words:
         if w[0:2]=='%(': # match a variable
            vname,vtype = w[2:].split(')')
            if vtype in conversions: fstring+= '\t\td["%s"]=%s(i.next())\n' % (vname, conversions[vtype])
            elif vtype == 's':
               fstring += '\t\ttemp = i.next()\n\t\tif temp[0] == "\\"":\n\t\t\ttemp = temp[1:]\n\t\t\twhile temp[-1]!="\\"": temp+=" "+i.next()\n\t\t\td["%s"]=temp[:-1].upper()\n' % vname
               fstring += '\t\telse: d["%s"]=temp.upper()\n' % vname
            elif vtype == 'ls':
               fstring += '\t\ttemp=""\n\t\tfor x in i: temp+= " "+x\n\t\td["%s"]=temp[1:]\n' % vname
         else: # else we must match a literal string
            fstring += '\t\tif i.next().upper()!="%s".upper(): return None\n' % w
      fstring += '\t\tdone=True\n'
      fstring += '\t\ti.next()\n' # this is to try and prompt a StopIteration exception, meaning the string has finished. If it isn't finished here, it's not a match
      fstring += '\t\treturn None\n'
      fstring += '\texcept (TypeError,ValueError): return None\n'
      fstring += '\texcept StopIteration:\n\t\tif done: return d\n\t\treturn None\n'
      #print fstring
      exec(fstring)
      self._match = func
      

   def format2regex(self,formatstring): # replaced by matchmaker (due to efficiency)
      """Extract a regular expression and variable names from a given format string.

      Warning: Currently somewhat simplistic, the only formats supported are:
       s : string
       ls: long string (eats spaces to the end of the line)
       qs: quoted string (matches "<string>")
       f : float
       d : integer
      """
      keys = {"s":r"\w+","d":r"-?\d+","e":r"-?\d+\.\d*[dDeE]?-?\d*","ls":r"[^\n\r]*","qs":r'"[^\n\r]*"'} # map of substitutions to make TODO: could make this a function argument
      members = []
      oldpos = 0
      restring = ""
      variter = re.finditer(r"%\(([^)]+)\)(\w+)", formatstring)
      for match in variter:
         members.append(match.group(1))
         sub = keys[match.group(2)]
         restring = restring + formatstring[oldpos:match.start()] + "(" + sub + ")"
         oldpos = match.end()
      restring = restring + formatstring[oldpos:]
      restring = re.sub(r"\s+",r"\s+",restring)
      return re.compile(restring), members

class Item:
   def __init__(self,blueprint,name=""):
      self.name = name
      self.blueprint = blueprint
   def read(self,fileiter):
      return self
   def __str__(self):
      if self.blueprint!='noblueprint':	#if it equals 'noblueprint' this is a special Item, not one directly created from a blueprint
                                        #thus we should not write it to the new file.
         return self.blueprint.writeout(self) + '\n' # TODO: the '\n' is for newline seperated blocks, for bracketed blocks some changes may be required
      return '' #null output (needs to be a string though, is trying to add to the file output string)
   def getcontent(self,name):
      if hasattr(self,"name") and self.name==name: return self
      return None
   def listify(self): return self.__dict__.values()
   #def dictify(self):
   #   if hasattr(self,"name"): return (self.name,self.__dict__)
   #   return None # probably should return something with a generic enumerated name

class Block:
   """Generic container for block data.

   Note: Block simply holds data, it does not define the structure of the data or how it is read from or written to files; that is the purpose of Blueprint."""
   def __init__(self,blueprint,name=""):
      self.blueprint = blueprint
      self.name = name
      self._contents = []
      self.indexed = {}

   def __getitem__(self,i):
      return self._contents[i]

   def append(self,val):	
      """Appends Item val to the ._contents list of the block and the .indexed dictionary (if it has an index)"""
      #print val.__class__	#val should always be an instance of class "Item"
      self._contents.append(val)
      if hasattr(val,'index'):
	 #if val.index==None:
          #  print 'appending ',val,
           # print 'with value',val.value
           #print 'to index ',val.index
	   #print 'of self ',self.name
         self.indexed[val.index] = val
      elif hasattr(val,'index0'):
         current = 1
         i = val.index0
         currdict = self.indexed
         while hasattr(val,'index%d'%current): # for array indexing
            if not i in currdict: currdict[i] = {}
            currdict = currdict[i]
            i = val.__dict__['index%d'%current]
            current += 1
         #print "currdict", currdict
         #print "val", val
         currdict[i] = val
      elif hasattr(val,'value'): #bjf> adding this to deal with blocks that have entries with no index
         #print 'ALPHA'
         #print val
         #print dir(val)
         #print self
         #print self.indexed
         #print 'appending ',val
         #print 'with value',val.value
	 #print 'of self ',self.name
         self.indexed['noindex'] = val  #store the value in the 'indexed' dictionary under the name 'noindex'.
         #note, this will OVERWRITE previous entries! If a situation is encountered where more than one Item
         #does not have an index in a block then only the last one will be stored!
         #print self.indexed['noindex'].value
         #print self.indexed['noindex'].name
         #print self.indexed
         #bjf> not sure what crazy consequences this might have...
      else:
         #print 'WARNING: Problem reading line in SLHA file, dumping variables...'
         #print 'val:', val
         pass

   def __str__(self):
      s = self.blueprint.writeout(self) + '\n' # TODO: the '\n' is for newline seperated blocks, for bracketed blocks some changes may be required
      for item in self._contents:
         s += str(item)
      return s

   def getcontent(self,name):
      if hasattr(self,'name') and self.name == name: return self
      for item in self._contents:
         temp = item.getcontent(name)
         if temp: 
            #print 'temp=',temp
            return temp
      return None

   def listify(self):
      return self.__dict__.values()+[item.listify() for item in self._contents]

   #def dictify(self):
   #   if hasattr(self,"name"): return dict([() for item in self.contents]) + self.__dict__

def construct(fileiter,*blueprints):
   l = []
   end = False
   while end == False:
      for blueprint in blueprints:
         item,end = blueprint.construct(fileiter)
         if item:
            l.append(item)
            break
      if item == None:
         try: fileiter.next()
         except StopIteration: break
   return l


