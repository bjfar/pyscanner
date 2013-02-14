from blockdata import *
from programs import SUSYFile

# TODO: there should be a dict from human readable string identifiers to SLHA integer identifiers.
# SLHAFile should use the integer ids to determine the correct item.

def genericitem(self,string):
   string,comment = string.split('#',1)
   formatstring = ''
   d={}
   values=0
   labels=0
   for word in string.split():
      f = fortfloat(word)
      if f:
         d['value'+values]=f
         formatstring += ' %(value%d)' % values
         values+=1
      else:
         d['label'+labels]=word
         formatstring += ' %(label%d)' % labels
         labels+=1
   if comment:
      d['name']=comment
      formatstring += ' # '+comment
   self.formatstring = formatstring
   return d

class SLHAFile(SUSYFile):
   def __init__(self,name,outputfrom=None,directory=None,items=[],customblocks=[],standardblocks=[]):
      #outputfrom is a 'program' object, directory is a string
      SUSYFile.__init__(self,name,outputfrom,directory)
      self.customblocks = customblocks
      itemtype1 = Blueprint(Item," %(index)d %(value)e # %(name)ls")
      itemtype2 = Blueprint(Item," %(index)d %(value)d # %(name)ls")   #bjf> be careful, this may incorrectly assume some entries are supposed to be integers if they happen to be an integer in the template. Ensure zero entries have a decimal place, i.e. 0.0e0 or similar
      itemtype3 = Blueprint(Item," %(index)d %(value)s # %(name)ls")
      itemtype4 = Blueprint(Item," %(index)d %(value)ls")    #bjf> I added this because it wasn't reading in lines with no comment. Works for strings only atm. Added to "items" list as well. Example: Softsusy output, block SPINFO, index 4, value "Point invalid: [ MuSqWrongsign ]", no name (as you call it).
      itemtype5 = Blueprint(Item," %(value)e # %(name)ls")   #bjf> needed for 'alpha' block of softsusy output, has only one entry, which has no index
      itemtype6 = Blueprint(Item," %(value)e")   #bjf> as above, but accounting for possibility that there is no comment
      #bjf> want an item that extracts values from block itself. Try the following:
      #itemtype7 = Blueprint(Block,"BLOCK %(name)s Q= %(value)e # %(comment)ls")
      #itemtype8 = Blueprint(Block,"BLOCK %(name)s Q=%(value)e # %(comment)ls") 
      #itemtype9 = Blueprint(Block,"BLOCK %(name)s Q= %(value)e")
      #<bjf
      blankitem = Blueprint(Item," %(index)d # %(name)ls")	
      commentline0 = Blueprint(Item,"# %(comment)ls")
      commentline = Blueprint(Item," # %(comment)ls")
      commentline2 = Blueprint(Item," #%(comment)ls")
      #itemtype5,itemtype6
      #itemtype7,itemtype8,itemtype9
      items += [itemtype2,itemtype1,itemtype3,itemtype4,itemtype5,itemtype6,
		blankitem,commentline0,commentline,commentline2] # the order here could make a difference to performance (should it be items+[ ] or [ ]+items?)
      blocktype1 = Blueprint(Block,"BLOCK %(name)s %(value)d # %(comment)ls")
      blocktype2 = Blueprint(Block,"BLOCK %(name)s # %(comment)ls")
      #WARNING!!! blocktype 3 didn't solve my problem: had lines in a file like:
      # Block CROSSSECTIONS   #LSP-nucleon spin independent (SI) and dependent (SD) sigmas
      #the lack of a space after the hash before the comment was killing the code; tried to add blocktype3
      #to compensate but didn't work. Had to changed the file to avoid problem. 
      blocktype3 = Blueprint(Block,"BLOCK %(name)s #%(comment)ls")  #bjf> spaces can cause errors apparently if not in the file
      #blocktype10 = Blueprint(Block,"Block %(name)s #%(comment)ls")  #bjf> spaces can cause errors apparently if not in the file
      blocktype4 = Blueprint(Block,"BLOCK %(name)s")
      blocktype5 = Blueprint(Block,"BLOCK %(name)s Q= %(value)e # %(comment)ls")    #bjf> added extra blocktype to deal with some of the softsusy blocks
      blocktype6 = Blueprint(Block,"BLOCK %(name)s Q=%(value)e # %(comment)ls")    #bjf> added extra blocktype to deal with some of the softsusy blocks
      blocktype7 = Blueprint(Block,"BLOCK %(name)s Q= %(value)e")    #bjf> Need one to have no comment as well
      #bjf> need blueprints to account for possible spaces before BLOCK
      standardblocks += [blocktype1,blocktype2,blocktype3,blocktype4,blocktype5,blocktype6,blocktype7]
      for block in standardblocks: block.subblueprints += items
      self.items = items
      self.standardblocks = standardblocks
   def readdata(self):
      #print 'IN READDATA'
      fi = FileIterator(self.fullpath())
      self.data = construct(fi,*self.customblocks+self.standardblocks)
   def update(self,inputs):
      self.readdata() # TODO: probably not needed now
      for key,val in inputs:
         self[key] = val
   def getcontent(self,key):
      for item in self.data:
         temp = item.getcontent(key)
         if temp: 
            #print 'returning temp...'
            #print 'in getcontent'
            #print 'item', item
            #print 'key', key
            #print 'temp', temp
            return temp
   def extract(self,key):
      """"""
      c = self.getcontent(key)
      if c: return c.value
      return None
   def __getitem__(self,i):
      return self.extract(i)
   def __setitem__(self,i,val):
      temp = self.getcontent(i)
      if hasattr(temp,"value"): temp.value = val
   def copyto(self,path):
      f = open(SUSYFile.add_suffix(path),"wb")
      # print 'slhacopying', SUSYFile.add_suffix(path)
      for block in self.data:
         f.write(str(block))
   def block(self,blockname,index=None,value=None):
      """Return either the block's index map or the value of the item corresponding to an index if provided, which is set to value if value is provided."""
      b = self.getcontent(blockname)
      #print 'in block'
      #print self
      #print self.name
      #print blockname
      #print index
      #print value
      #print b
      #print b.indexed
      #if index!=None:
      #   print 'value:',b.indexed[index].value
      if not b: return None
      if index!=None:   #DAMMIT DANIEL!!! IF AN INDEX IS 0 IT COUNTS AS FALSE!!! "if index:" IS BAD CODE!
         #print b.indexed[index]
         try: b.indexed[index]	#see if the index can be accessed
         except KeyError:
		msg="Error, no observable at the given index found in this block: \
Program may not have generated it (file:{0}, index:{1}, block:{2})".format(self.name,index,blockname)
                raise KeyError(msg)
         if value!=None: 
            #print b.indexed[index].value
            b.indexed[index].value = value   
         return b.indexed[index].value
      return b.indexed

class OmegaFile(SLHAFile):
   def __init__(self,name,outputfrom=None,directory=None):
      items = [Blueprint(Item,"%(value)s %(index0)s %(index1)s -> %(index2)s %(index3)s")]
      items.append(Blueprint(Item,"%(value)e # %(name)ls"))
      items.append(Blueprint(Item,"%(particle)s = %(composition)s"))
      SLHAFile.__init__(self,name,outputfrom,directory,items)

class DecayFile(SLHAFile):
    def __init__(self,name,directory):
        decayitem = Blueprint(Item," %(value)e %(index0)d %(index1)d %(index2)d # %(name)ls")
        decayblock = Blueprint(Block,"DECAY %(name)d %(width)e # %(comment)ls",[decayitem])
        SLHAFile.__init__(self,name,directory,customblocks=[decayblock])

class SpectrumFile(SLHAFile): #bjf> passed more arguments through to SLHAFile constructor
    def __init__(self,name,outputfrom=None,directory=None):
        items = [Blueprint(Item," %(index0)d %(index1)d %(value)e # %(name)ls")]
        valblock = Blueprint(Block,"BLOCK %(name)s %(var0)s %(value)e # %(comment)ls")
        SLHAFile.__init__(self,name,outputfrom,directory,items,standardblocks=[valblock])
        
class FlavourFile(SLHAFile): #bjf> designed to read flavour physics blocks in SuperIso output
    def __init__(self,name,outputfrom=None,directory=None):
        items = [
            Blueprint(Item," %(index0)d %(index1)d %(value)e %(index2)d %(index3)d %(index4)d %(index5)d %(index6)d # %(name)ls"),
            Blueprint(Item," %(index0)d %(index1)d %(value)e %(index2)d %(index3)d %(index4)d %(index5)d # %(name)ls"),
            ]
        SLHAFile.__init__(self,name,outputfrom,directory,items,standardblocks=[])
        
'''
class LHCFile(SLHAFile):
    def __init__(self,name,dirctory):
        channelitem = Blueprint(Item,"%(value)e # %(index)ls")
        higgsblock = Blueprint(Block,"# %(name)s",[channelitem])
        SLHAFile.__init__(self,name,directory,items,customblocks=[higgsblock])
        self.standardblocks = []
'''


        
