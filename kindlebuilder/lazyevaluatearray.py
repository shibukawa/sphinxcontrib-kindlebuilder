# encoding: utf-8

import time
import struct
import uuid

class VirtualChunk(object):
    def __init__(self, length):
        self.length = length
    
    def convert(self, value):
        if self.length == 1:
            return struct.pack("!B", value)
        elif self.length == 2:
            return struct.pack("!H", value)
        elif self.length == 4:
            return struct.pack("!I", value)
    
    def __len__(self):
        return self.length
        
    def write(self, writer, lazyarray):
        raise NotImplemented()


class LengthFlag(VirtualChunk):
    def __init__(self, length, begin_key, end_key):
        self.begin_key = begin_key
        self.end_key = end_key
        super(LengthFlag, self).__init__(length)
        
    def write(self, writer, lazyarray):
        end = lazyarray.find_position(self.end_key)
        begin = lazyarray.find_position(self.begin_key)
        if end is None and begin is None:
            raise ValueError("position key: '%s' and '%s' is not defined" % (
                self.begin_key, self.end_key))
        elif end is None:
            raise ValueError("position key: '%s' is not defined" % (
            	self.end_key))
        elif begin is None:
            raise ValueError("position key: '%s' is not defined" % (
                self.begin_key))
        writer.write(self.convert(end - begin))
    
    def dump(self):
        return "Length: %s - %s" % (self.begin_key, self.end_key)


class OffsetFlag(VirtualChunk):
    def __init__(self, length, key, format=None):
        self.key = key
        self.format = format
        super(OffsetFlag, self).__init__(length)
    
    def write(self, writer, lazyarray):
        position = lazyarray.find_position(self.key)
        if position is None:
            raise ValueError("position key: '%s' is not defined" % (self.key))
        if self.format:
            writer.write(self.format % position)
        else:
            writer.write(self.convert(position))

    def dump(self):
        return "Offset: %s" % self.key


class Variable(VirtualChunk):
    def __init__(self, key, length, format=None):
        self.key = key
        self.format = format
        super(Variable, self).__init__(length)

    def write(self, writer, lazyarray):
        value = lazyarray.find_variable(self.key)
        if value is None:
            raise ValueError("variable key: '%s' is not defined" % (self.key))
        if isinstance(value, (int, long)):
            if self.format:
                writer.write(self.format % value)
            else:
                writer.write(self.convert(value))
        else:
            writer.write(value)
            for i in range(self.length - len(value)):
                writer.write('\0')

    def dump(self):
        return "Variable: %s" % self.key


class Label(object):
    def __init__(self, key):
        self.key = key
        self.position = None

    def write(self, writer, lazyarray):
        pass
    
    def __len__(self):
        return 0

    def dump(self):
        return "Label: %s" % self.key


class DataChunk(object):
    def __init__(self, data):
        self.data = data
    
    def write(self, writer, lazyarray):
        writer.write(self.data)
    
    def __len__(self):
        return len(self.data)

    def dump(self):
        if len(self.data) < 30:
            return self.data
        return self.data[:29]


class LazyEvaluateArray(object):
    def __init__(self, parent = None, args=[]):
        self._chunks = []
        if parent:
            self._positions = parent._positions
            self._variables = parent._variables
            self._lock = parent._lock
        else:
            self._positions = {}
            self._variables = {}
            self._lock = []
        self.parent = parent
        self.init(*args)
    
    def init(self):
        pass

    def lock_check(self):
        if self._lock:
            raise RuntimeError(("can't modify array any more. "
                                "this array is locked"))

    def find_position(self, key):
        return self._positions.get(key)
        
    def find_variable(self, key):
        return self._variables.get(key)
    
    def set_variable(self, key, value):
        self._variables[key] = value
    
    def length(self, start_key, end_key, length):
        self.lock_check() 
        self._chunks.append(LengthFlag(length, start_key, end_key))
    
    def offset(self, key, length, format=None):
        self.lock_check()
        self._chunks.append(OffsetFlag(length, key, format))

    def variable(self, key, length=4, format=None, default=None):
        self.lock_check()
        self._chunks.append(Variable(key, length, format))
        if default is not None:
            self.set_variable(key, default)
    
    def label(self, key):
        self.lock_check()
        self._chunks.append(Label(key))
    
    def append(self, data):
        self.lock_check()
        self._chunks.append(DataChunk(data))
    
    def data(self, data, *args):
        self.lock_check()
        if args:
            data = struct.pack(data, *args)
        self._chunks.append(DataChunk(data))
    
    def sub_array(self, array_type=None, args=[]):
        self.lock_check()
        if array_type is None:
            array_type = LazyEvaluateArray
        new_array = array_type(self, args)
        self._chunks.append(new_array)
        return new_array
    
    def reserve(self, code, length):
        self.lock_check()
        for i in range(length):
            self.data("B", code)

    def unique_number(self, length=4):
        return int(uuid.uuid4().int % 2 ** (length*8))

    def _calc_position(self, offset=0):
        for chunk in self._chunks:
            if isinstance(chunk, Label):
                #print "%07d:" % offset, chunk.key
                self._positions[chunk.key] = offset
            elif isinstance(chunk, LazyEvaluateArray):
                offset = chunk._calc_position(offset)
            else:
                offset += len(chunk)
        return offset
   
    def lock(self):
        self._calc_position()
        self._lock.append(True)
        for key, value in self._variables.items():
            print "%20s:" % key, value


    def write(self, writer, dummy=None):
        if not self._lock:
            raise RuntimeError(("This array is not locked. "
                                "Run lock() method first"))
        [chunk.write(writer, self) for chunk in self._chunks]

    def as_list(self):
        output = OutputAsList()
        self.write(output)
        return output.result
    
    def __iter__(self):
        for chunkstr in self.as_list():
            yield chunkstr

    def dump(self, indent=0):
        output_data = False
        for chunk in self._chunks:
            if isinstance(chunk, (DataChunk, str, unicode)):
                if not output_data:
                    if isinstance(chunk, (str, unicode)):
                        print "  " * indent, chunk
                    else:
                        print "  " * indent, chunk.dump()
                output_data = True
            elif isinstance(chunk, LazyEvaluateArray):
                chunk.dump(indent + 1)
            else:
                output_data = False
                print "  " * indent, chunk.dump()

class OutputAsList(object):
    def __init__(self):
        self.result = []

    def write(self, content):
        self.result.append(content)

