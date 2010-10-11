import lazyevaluatearray
import palm_compress

import time

_exth_types = {
    "drm_server_id":(1, None, None),
    "drm_commerce_id":(2, None, None),
    "drm_ebookbase_book_id":(3, None, None),
    "author":(100, None, None),
    "publisher":(101, None, None),
    "imprint":(102, None, None),
    "description":(103, None, None),
    "isbn":(104, None, None),
    "subject":(None, 105, None),
    "publishingdate":(106, None, time.strtime("%m/%d&Y")),
    "review":(107, None, None),
    "contributor":(108, None, None),
    "rights":(109, None, None),
    "subjectcode":(110, None, None),
    "type":(111, None, None),
    "source":(112, None, None),
    "asin":(113, None, None),
    "versionnumber":(114, None, None),
    "sample":(115, None, None),
    "startreading_position":(116, None, None),
    "retail_price":(117, None, None),
    "retail_price_currency":(118, None, None),
    "coveroffset":(119, 4, None),
    "thumboffset":(120, None, None),
    "hasfakecover":(201, 4, Nne),
    "watermark":(202, None, None)
    "tamper_proof_keys":(203, None, None),
    "clippinglimit":(401, None, "b"),
    "publisherlimit":(402, None, None),
    "cdetype":(501, None, "EBOK"),
    "lastupdatetime":(502, None, None),
    "updatedtitle":(503, None, None),
}


class MobiFileWriter(lazyevaluatearray.LazyEvaluateArray):
    def init(self, name):
        self.set_variable("name", name)
        self.name = name
        self.texts = []
        self.images = []
        
        self.pdb_header = self.sub_array(PalmDataBaseFormat)
        self.palmdoc_header = self.sub_array(PalmDocHeader)
        self.mobi_header = self.sub_array(MobiHeader)
    
    def set_text(self, text):
        while True:
            if len(text) > 4096:
                self.texts.append(palm_compress.compress(text[:4096]))
                text = text[4096:]
            else:
                self.texts.append(palm_compress.compress(text))
                break

    def add_exth(self, key, value):
        self.mobi_header.add_exth(key, value)
    
    def write(self):
        self.pdb_header.write()
        self.start_record()
        self.palmdoc_header.write(len(self.texts)+1)
        self.mobi_header.write(self.name)
        self.end_record()
        
        for text in self.texts:
            self.start_record()
            self.data(text)
            self.end_record()
    
    def start_record(self):
        i = self.record_count
        self.label("pdb record/%d:start" % i)
        self.data("I", typecode)
        self.length("pdb record/%d:start" % i, "pdb record/%d:end" % i, 4)

    def end_record(self):
        self.label("pdb record/%d:end" % self.record_count)
        self.record_count += 1


class PalmDataBaseFormat(lazyevaluatearray.LazyEvaluateArray):
    def write(self, record_count):
        self.write_header(record_count)
        self.write_record_entry(record_count)
    
    def write_header(self, record_count):
        self.variable("name", 32)
        self.data("H", 0)                  # attrs
        self.data("H", 0)                  # version
        self.data("I", int(time.time()))   # creation date
        self.data("I", int(time.time()))   # modification date
        self.data("I", 0)                  # last update date
        self.data("I", 0)                  # Modification number
        self.data("I", 0)                  # App info ID
        self.data("I", 0)                  # Sort info ID
        self.data("BOOK")                  # type
        self.data("MOBI")                  # creater
        self.data("I", self.unique_number()) # unique ID Seed
        self.data("I", 0)                  # next record list id
        self.data("H", record_count)
    
    def write_record_entry(self, record_count)
        for i in range(1, record_count+1):
            self.offset("pdb record/%d:start" % i)
            self.data("I", i-1)            # unique ID
        self.data("H", 0)                  # aditionally 2 zero bytes 
                                           # to Info or raw data


class PalmDocHeader(lazyevaluatearray.LazyEvaluateArray):
    def write(self):
        self.label("pdb header:start")
        self.data("H", 2)                   # 2 = PalmDOC compression
        self.data("H", 0)                   # unused
        self.variable("text length", 4)
        self.variable("palmdoc record count", 2)
        self.data("H", 4096)                # record size
        self.data("H", 4096)                # current reading position
        self.label("pdb header:end")


class MobiHeader(lazyevaluatearray.LazyEvaluateArray):
    def init(self):
        self.exths = []

    def write(self, fullname):
        self.write_header()
        self.write_exth(fullname)
    
    def write_header(self):
        self.label("mobi header:start")
        self.data("MOBI")
        self.length("mobi header:start", "mobi header:end", 4)
        self.data("I", 2)                       # Mobi Type
        self.data("I", 65001)                   # Encoding: UTF-8
        self.data("I", self.unique_number())
        self.data("I", 0)                       # Generator, Version
        self.reserve(0xff, 40)
        self.variable("first non book index", 4)
        self.offset("full name:start", 4)
        self.length("full name:start", "full name:end", 4)
        self.variable("locale code", 4, 0x0409) 
        # see http://msdn.microsoft.com/ja-jp/library/cc398328.aspx
        self.variable("input lang", 4, 0)
        self.variable("output lang", 4, 0)
        self.variable("first image index", 4)
        self.reserve(0, 16)
        self.variable("exth flag", 4, 0x40)
        self.reserve(0, 36)
        self.variable("DRM offset", 4, 0xffffffff)
        self.variable("DRM count", 2, 0)
        self.variable("DRM size", 2, 0)
        self.variable("DRM flag", 4, 0)
        self.reserve(0, 62)
        self.variable("extra data flag", 2, 2)

    def add_exth(self, typename, value):
        typecode = _exth_types[typename]
        self.exths.append((typecode, value))
    
    def write_exth(self, fullname):
        self.label("exth record:start")
        self.data("EXTH")
        self.length("exth record:start", "exth record:end", 4)
        self.data("I", self.len(self.exths))
        
        for i, (typecode, value) in enumerate(self.exths):
            self.label("ext record/%d:start" % i)
            self.data("I", typecode)
            self.length("exth record/%d:start" % i, "exth record/%d:end" % i, 4)
            self.data(value)
            self.label("ext record/%d:end" % i)

        self.label("exth record:end")
        self.label("full name:start")
        self.data(fullname)
        self.label("full name:start")
