# -*- encoding: sjis -*-

import collections
import array

def compress(bytes):
    chunks = collections.deque()
    position = len(bytes)
    while position > 0:
        windowchunk = window(bytes, position)
        textchunk = text(bytes, windowchunk.last, position)
        if textchunk:
            chunks.appendleft(textchunk)
        if windowchunk:
            chunks.appendleft(windowchunk)
        else:
            chunks.appendleft(text(bytes, 0, position))
        position = windowchunk.start
    byte_array = array.array('B')
    [chunk.write(byte_array) for chunk in chunks]
    return byte_array.tostring()


class window(object):
    def __init__(self, bytes, position):
        self.last = position
        self.find = False
        self.bytes = bytes
        while position >= 3:
            index, length = self.search_window(position)
            if length:
                self.start = position - length
                self.offset = self.start - index
                self.last = position
                self.find = True
                break
            position -= 1
        else:
            self.start = 0

    def write(self, byte_array):
        print str(self),
        length = self.last - self.start
        bytes = 0x80 * 256 + ((self.offset) << 3) + length - 3
        byte_array.append(bytes >> 8)
        byte_array.append(bytes & 0xff)
        
    def __str__(self):
        return "<%s, %d, %d>" % (self.bytes[self.start-self.offset:self.last-self.offset], 
            self.offset, self.last-self.start)

    def __nonzero__(self):
        return self.find 
       
    def search_window(self, position): 
        for length in xrange(10, 2, -1):
            end_point = position - length
            if end_point < length:
                break
            start_point = max(0, end_point - 2048)
            search_word = self.bytes[position-length:position]
            index = self.bytes.rfind(search_word, start_point, end_point)
            if index != -1:
                return index, length
        return None, None


class text(object):
    OTHER = 0
    TYPE_A = 1
    TYPE_C = 2
    
    def __init__(self, bytes, start, end):
        self.start = start
        self.end = end
        self.bytes = bytes
        self.array = array.array('B')
        self.compress(bytes[start:end])
    
    def _check_type(self, bytes, index):
        first = ord(bytes[index])
        if first == 32:
            try:
                second = ord(bytes[index+1])
            except IndexError:
                pass
            else:
                if second in xrange(64, 128):
                    return self.TYPE_C, 0x80 ^ second
        if first == 0 or first in xrange(9, 127):
            return self.OTHER, first
        return self.TYPE_A, first
    
    def _type_a(self, bytes, index):
        code = ord(bytes[index])
        if code == 0 or code in xrange(9, 127):
            return code
        else:
            return None
    
    def compress(self, bytes):
        type_a = []
        skip = False
        def merge_buffer():
            if type_a:
                self.array.append(len(type_a))
                [self.array.append(code) for code in type_a]
                del type_a[:]

        for i in xrange(len(bytes)):
            if skip:
                skip = False
                continue
            type, code = self._check_type(bytes, i)
            if type == self.TYPE_C:
                merge_buffer()
                self.array.append(code)
                skip = True
            elif type == self.TYPE_A:
                type_a.append(code)
                if len(type_a) == 8:
                    merge_buffer()
            else:
                if type_a:
                    type_a.append(code)
                    if len(type_a) == 8:
                        merge_buffer()
                else:
                    self.array.append(code)
        merge_buffer()
    
    def write(self, byte_array):
        print str(self),
        [byte_array.append(char) for char in self.array]

    def __nonzero__(self):
        return self.start != self.end
    
    def __str__(self):
        return self.bytes[self.start:self.end]


def decompress(bytes):
    blen = len(bytes)
    bytes = [ord(c) for c in bytes] # comvert byte to int array
    result_array = array.array('B')
    outlen = 6000
    i = 0
    j = 0
    while i < blen:
        c = bytes[i]
        i += 1
        if c >= 0xc0:
            # "Type C" command
            result_array.append(32) # ' '
            result_array.append(c & 0x7f)
            j += 2
        elif c >= 0x80:
            # "Type B" command
            c = (c << 8) | bytes[i]
            i += 1
            wdist = (c >> 3) & 0x07ff # Slide window position
            wcopy = j - wdist # Output buffer and slide window
            wlen = min((c & 7) + 3, outlen - j)
            for _ in xrange(0, wlen):
                result_array.append(result_array[wcopy])
                j += 1
                wcopy += 1

        elif c >= 0x09:
            # Single output
            result_array.append(c)
            j += 1

        elif c >= 0x01:
            # Repeated output
            c = min(c, outlen - j)
            for _ in xrange(0, c):
                result_array.append(bytes[i])
                i += 1
                j += 1
   
        else:
            # Single output
            result_array.append(c)
            j += 1

    return result_array.tostring()


def test():
    zen_of_python = """Beautiful is better than ugly.
    Explicit is better than implicit.
    Simple is better than complex.
    Complex is better than complicated.
    Flat is better than nested.
    Sparse is better than dense.
    Readability counts.
    Special cases aren't special enough to break the rules.
    Although practicality beats purity.
    Errors should never pass silently.
    Unless explicitly silenced.
    In the face of ambiguity, refuse the temptation to guess.
    There should be one-- and preferably only one --obvious way to do it.
    Although that way may not be obvious at first unless you're Dutch.
    Now is better than never.
    Although never is often better than *right* now.
    If the implementation is hard to explain, it's a bad idea.
    If the implementation is easy to explain, it may be a good idea.
    Namespaces are one honking great idea -- let's do more of those!
    """
    sample = zen_of_python
    sample = "あいうえお          あいうえお日本語"
    archive = compress(sample)
    result = decompress(archive)
    print
    print "=" * 78
    print repr(sample)
    print "-" * 78
    if sample == result:
        print "OK"
    else:
        print repr(result)

if __name__ == "__main__":
    test()
