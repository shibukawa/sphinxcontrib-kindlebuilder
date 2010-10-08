import time
import struct
import uuid

class VirtualChunk(object):
    def __init__(self, length):
        self.length = length
    
    def convert(length, value):
        if self.length == 1:
            return struct.pack("B", value)
        elif self.length == 2:
            return struct.pack("H", value)
        elif self.length == 4:
            return struct.pack("I", value)
    
    def __len__(self):
        return self.length


class LengthFlag(VirtualChunk):
    def __init__(self, length, begin_key, end_key):
        self.begin_key = begin_key
        self.end_key = end_key
        super(LengthFlag, self).__init__(length)
        
    def write(self, virtualbuffer):
        end = virtualbuffer.find_position(self.end_key)
        start = virtualbuffer.find_position(self.start_key)
        return self.convert(end - start)


class OffsetFlag(VirtualChunk):
    def __init__(self, length, position_key):
        self.position_key = position_key
        super(LengthFlag, self).__init__(length)
    
    def write(self, virtualbuffer):
        position = virtualbuffer.find_position(self.position_key)
        return self.convert(position)


class Variable(VirtualChunk):
    def __init__(self, key, length, format=None):
        self.key = key
        self.format = format
        super(LengthFlag, self).__init__(length)

    def write(self, virtualbuffer):
        if self.format:
            return self.format % virtualbuffer.find_variable(self.key)
        return self.convert(virtualbuffer.find_variable(self.key))


class Label(object):
    def __init__(self, key):
        self.key = key
        self.position = None

    def write(self, virtualbuffer):
        return ""
    
    def __len__(self):
        return 0


class DataChunk(object):
    def __init__(self, data):
        self.data = data
    
    def write(self, virtualbuffer):
        return self.data
    
    def __len__(self):
        return len(self.data)


class LasyEvaluateArray(object):
    def __init__(self, parent = None):
        self._chunks = []
        if parent:
            self._positions = parent._positions
            self._variables = parent._variables
        else:
            self._positions = {}
            self._variables = {}
    
    def find_position(self, key):
        return self._positions[key]
        
    def find_variable(self, key):
        return self._variables[key]
    
    def set_variable(self, key, value):
        self._variables[key] = value
    
    def calc_position(self):
        offset = 0
        for chunk in self._chunks:
            if isinstance(chunk, Label):
                self._positions[chunk.key] = offset
            else:
                offset += len(chunk)
    
    def length(self, start_key, end_key, length):
        self._chunks.append(LengthFlag(length, start_key, end_key))
    
    def offset(self, key, length):
        self._chunks.append(OffsetFlag(length, key))

    def variable(self, key, length=4, default=None):
        self._chunks.append(Variable(key, length))
        if default is not None:
            self.set_variable(key, default)
    
    def variable_with_format(self, key, format, default=None):
        self._chunks.append(Variable(key, format = format))
    
    def label(self, key):
        self._chunks.append(Label(key))
    
    def append(self, data):
        self._chunks.append(DataChunk(data))
    
    def data(self, data, *args):
        if args:
            data = struct(data, *args)
        self._chunks.append(DataChunk(data))
    
    def new_buffer(self):
        new_buffer = VirtualBuffer(self)
        self._chunks.append(new_buffer)
        return new_buffer
    
    def reserve(self, code, length):
        for i in range(length):
            self._chunks.data("b", code)

    def unique_number(self, length=4):
        return int(uuid.uuid4().int % 2 ** (length*8))
