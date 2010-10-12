
import time

from lazyevaluatearray import LazyEvaluateArray
import palm_compress


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
    "publishingdate":(106, None, time.strftime("%m/%d&Y")),
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
    "hasfakecover":(201, 4, None),
    "watermark":(202, None, None),
    "tamper_proof_keys":(203, None, None),
    "clippinglimit":(401, None, "b"),
    "publisherlimit":(402, None, None),
    "cdetype":(501, None, "EBOK"),
    "lastupdatetime":(502, None, None),
    "updatedtitle":(503, None, None),
}


class MobiFileGenerator(LazyEvaluateArray):
    def init(self):
        self.name = None
        self.texts = []
        self.images = []
        self.cover_image = None
        self.record_count = 1
        
        self.pdb_header = self.sub_array(PalmDataBaseFormat)
        self.palmdoc_header = self.sub_array(PalmDocHeader)
        self.mobi_header = self.sub_array(MobiHeader)

    def set_name(self, name):
        self.name = name
        self.set_variable("name", name)
    
    def set_text(self, text):
        while True:
            if len(text) > 4096:
                self.texts.append(palm_compress.compress(text[:4096]))
                text = text[4096:]
            else:
                self.texts.append(palm_compress.compress(text))
                break
    
    def set_images(self, images):
        self.images = images
        
    def set_cover_image(self, image_path):
        self.cover_image = image_path

    def add_exth(self, key, value):
        self.mobi_header.add_exth(key, value)
    
    def generate(self, output_folder, basename):
        self.pdb_header.generate()
        self.start_record()
        self.palmdoc_header.generate()
        
        if self.cover_image:
            self.add_exth("coveroffset", 
                len(self.texts) + len(self.images) + 2)
            self.set_variable("pdb record count", 
                len(self.texts) + len(self.images) + 3)
        else:
            self.set_variable("pdb record count", 
                len(self.texts) + len(self.images) + 2)
        self.set_variable("palmdoc record count", len(self.texts))
        self.set_variable("first non book index", len(self.texts)+2)
        self.set_variable("first image index", len(self.texts)+2)
        
        
        self.mobi_header.generate(self.name)
        self.end_record()
        
        for text in self.texts:
            self.start_record()
            self.data(text)
            self.data("B", 0)
            self.end_record()
        
        for image in self.images:
            self.start_record()
            self.data(image)
            self.end_record()
        
        if self.cover_image:
            self.start_record()
            self.data(open(self.cover_image, "rb"))
            self.end_record()
        
        self.generate_eof_record()
        
        self.calc_position()
        
        content = self.write()
        file = open(os.path.join(output_folder, basename + ".azw"), "bw")
        file.write(content)
        file.close()
        
    def start_record(self):
        i = self.record_count
        self.label("pdb record/%d:start" % i)
        self.data("B", 0)
        self.length("pdb record/%d:start" % i, "pdb record/%d:end" % i, 4)
        self.pdb_header.append_record_entry(i)

    def end_record(self):
        self.label("pdb record/%d:end" % self.record_count)
        self.record_count += 1

    def generate_eof_record(self):
        self.start_record()
        self.data("B", 233)
        self.data("B", 142)
        self.data("B", 13)
        self.data("B", 10)
        self.end_record()


class PalmDataBaseFormat(LazyEvaluateArray):
    def generate(self):
        self.generate_header()
    
    def generate_header(self):
        self.variable("name", 32, u"%-32s")
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
        self.variable("pdb record count", 2)
        self.record_entries = self.sub_array()
        self.data("H", 0)                  # aditionally 2 zero bytes
    
    def append_record_entry(self, record_index):
        self.record_entries.offset("pdb record/%d:start" % record_index, 4)
        self.record_entries.data("I", record_index-1) # unique ID


class PalmDocHeader(LazyEvaluateArray):
    def generate(self):
        self.label("pdb header:start")
        self.data("H", 2)                   # 2 = PalmDOC compression
        self.data("H", 0)                   # unused
        self.variable("text length", 4)
        self.variable("palmdoc record count", 2)
        self.data("H", 4096)                # record size
        self.data("H", 0)                   # current reading position
        self.label("pdb header:end")


class MobiHeader(LazyEvaluateArray):
    def init(self):
        self.exths = {}
        for key, (typeid, format, default) in _exth_types.items():
            if default is not None:
                self.exths[key] = default

    def generate(self, fullname):
        self.generate_header()
        self.generate_exth(fullname)
    
    def generate_header(self):
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
        self.variable("locale code", 4, default=0x0409) 
        # see http://msdn.microsoft.com/ja-jp/library/cc398328.aspx
        self.variable("input lang", 4, default=0)
        self.variable("output lang", 4, default=0)
        self.variable("first image index", 4)
        self.reserve(0, 16)
        self.variable("exth flag", 4, default=0x40)
        self.reserve(0, 36)
        self.variable("DRM offset", 4, default=0xffffffff)
        self.variable("DRM count", 2, default=0)
        self.variable("DRM size", 2, default=0)
        self.variable("DRM flag", 4, default=0)
        self.reserve(0, 62)
        self.variable("extra data flag", 2, default=0)

    def add_exth(self, typename, value):
        if typename in _exth_types:
            self.exths[typename] = value
        else:
            raise KeyError("%s is not in valid exth name" % typename)
    
    def generate_exth(self, fullname):
        self.label("exth record:start")
        self.data("EXTH")
        self.length("exth record:start", "exth record:end", 4)
        self.data("I", len(self.exths))
        
        for i, (typename, value) in enumerate(self.exths.items()):
            self.label("ext record/%d:start" % i)
            self.data("I", _exth_types[typename][0])
            self.length("exth record/%d:start" % i, "exth record/%d:end" % i, 4)
            self.data(value)
            self.label("ext record/%d:end" % i)

        self.label("exth record:end")
        self.label("full name:start")
        self.data(fullname)
        self.label("full name:start")
