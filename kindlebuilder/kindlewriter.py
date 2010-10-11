
from docutils import nodes
from docutils.writers.html4css1 import Writer, HTMLTranslator
from lasyevaluatearray import LasyEvaluateArray


class KindleHTMLWriter(Writer):
    supported = ('html',)

    visitor_attributes = (
        'body_pre_docinfo', 'docinfo', 'body',
        'title', 'subtitle', 'fragment', 'pictures',
        'whole_contents')
    
    def __init__(self, builder):
        print "KindleHTMLWriter"
        Writer.__init__(self)
        self.builder = builder
        self.translator_class = KindleHTMLTranslator

    def get_transforms(self):
        return writers.Writer.get_transforms(self) + [writer_aux.Admonitions]

    def translate(self):
        # sadly, this is mostly copied from parent class
        self.visitor = visitor = self.translator_class(self.builder,
                                                       self.document)
        self.document.walkabout(visitor)
        self.output = visitor.astext()
        for attr in self.visitor_attributes:
            setattr(self, attr, getattr(visitor, attr, None))
        self.visitor.whole_contents.dump()


class KindleReferenceWriter(LasyEvaluateArray):
    def add_reference(self, title, type):
        label = "kindle special reference: %s" % type
        self.append('<reference title="%s" type="%s" filepos=' % (title, type))
        self.offset(label, 10, "%010d")
        self.append(' />')
        
        self.parent.label(label)
        self.parent.append("<h1><b>%s</b></h1> <br>" % title)


class KindleHeadingWriter(LasyEvaluateArray):
    def init(self):
        self.last_index = 1
        self.last_level = 0
    
    def visit(self, level, title):
        index = self.last_index
        self.last_index += 1
        
        label = "kindle heading: %s-%s" % (index, level)
        print label
        
        if level in (1, 2):
            if self.last_level > 2 and index != 1:
                self.append("</ul></p></br>")
            if level == 1:
                self.append("<h3><b><a filepos=")
                self.offset(label, 10, "%010d")
                self.append(" >%s</a></b></h3><br>" % title)
                if index != 1:
                    self.parent.append("<mbp:pagebreak/>")
                self.parent.label(label)
                self.parent.append("<h1><b>%s</b></H1>" % title)
            elif level == 2:
                self.append("<a filepos=")
                self.offset(label, 10, "%010d")
                self.append(" ><b>%s</b></a><br>" % title)

                if self.last_level != 1:
                    self.parent.append('<div height="24"></div>')
                self.parent.label(label)
                self.parent.append("<a></A> <h2>%s</H2>" % title)
        elif level == 3:
            if self.last_level != 3:
                self.append("<p><ul>")
            self.append("<a filepos=")
            self.offset(label, 10, "%010d")
            self.append(" >%s</a><br>" % title)

            self.parent.label(label)
            self.parent.append("<a></A> <h3>%s</H3>" % title)
        elif level in (4, 5, 6):
            self.parent.append("<a></A> <h%d>%s</H%d>" % (level, title, level))
        self.last_level = level
    
    def depart(self, level):
        print "depart title", level



class KindleHTMLTranslator(HTMLTranslator):
    def __init__(self, builder, document):
        nodes.NodeVisitor.__init__(self, document)
        self.builder = builder
        self.settings = settings = document.settings
        # document title, subtitle display
        self.body_pre_docinfo = []
        # author, date, etc.
        self.docinfo = []
        
        self.whole_contents = LasyEvaluateArray()
        self.body, self.reference, self.headings = self.initial_contents()
        
        self.fragment = []
        self.section_level = 0
        self.context = []
        self.topic_classes = []
        self.colspecs = []
        self.compact_p = 1
        self.compact_simple = None
        self.compact_field_list = None
        self.in_docinfo = None
        self.in_sidebar = None
        self.title = []
        self.subtitle = []
        self.in_document_title = 0
        self.in_mailto = 0
        self.author_in_authors = None
        
        self.kindle_title = None
        self.pictures = []
    
    def initial_contents(self):
        self.whole_contents.append("<html><head><guide>")
        reference = self.whole_contents.sub_array(KindleReferenceWriter)
        self.whole_contents.append("</buide></head><body>")
        reference.add_reference("Table of Contents", "toc")
        
        headings = self.whole_contents.sub_array(KindleHeadingWriter)
        
        self.whole_contents.append("<p><center><h1><big>* * *</big></h1></center></p>  <mbp:pagebreak/>")
        reference.add_reference("Start", "start")
        body = self.whole_contents.sub_array()
        headings.parent = body
        self.whole_contents.append("</body></html>")
        return body, reference, headings

    def astext(self):
        self.fragment.extend(self.body.as_list())
        return self.whole_contents.join()

    def visit_document(self, node):
        self.kindle_title = node.get('title', '')
        return

    def depart_document(self, node):
        assert not self.context, 'len(context) = %s' % len(self.context)
        self.fragment.extend(self.body.as_list())

    def visit_section(self, node):
        self.section_level += 1
        self.body.append('<p height="0" width="0em">')

    def depart_section(self, node):
        self.section_level -= 1
        self.body.append('</p>')

    def visit_start_of_file(self, node):
        # only occurs in the single-file builder
        pass
    def depart_start_of_file(self, node):
        self.body.append("<mbp:pagebreak/>")

    # not support in Kindle
    
    def visit_header(self, node):
        pass
    def depart_header(self, node):
        pass

    def visit_footer(self, node):
        pass
    def depart_footer(self, node):
        pass

    def visit_comment(self, node):
        raise nodes.SkipNode

    def visit_image(self, node):
        atts = {}
        uri = node['uri']
        # place SVG and SWF images in an <object> element
        types = {'.svg': 'image/svg+xml',
                 '.swf': 'application/x-shockwave-flash'}
        ext = os.path.splitext(uri)[1].lower()
        if ext in ('.svg', '.swf'):
            atts['data'] = uri
            atts['type'] = types[ext]
        else:
            atts['src'] = uri
            atts['alt'] = node.get('alt', uri)
        # image size
        if 'width' in node:
            atts['width'] = node['width']
        if 'height' in node:
            atts['height'] = node['height']
        if 'scale' in node:
            if Image and not ('width' in node and 'height' in node):
                try:
                    im = Image.open(str(uri))
                except (IOError, # Source image can't be found or opened
                        UnicodeError):  # PIL doesn't like Unicode paths.
                    pass
                else:
                    if 'width' not in atts:
                        atts['width'] = str(im.size[0])
                    if 'height' not in atts:
                        atts['height'] = str(im.size[1])
                    del im
            for att_name in 'width', 'height':
                if att_name in atts:
                    match = re.match(r'([0-9.]+)(\S*)$', atts[att_name])
                    assert match
                    atts[att_name] = '%s%s' % (
                        float(match.group(1)) * (float(node['scale']) / 100),
                        match.group(2))
        style = []
        for att_name in 'width', 'height':
            if att_name in atts:
                if re.match(r'^[0-9.]+$', atts[att_name]):
                    # Interpret unitless values as pixels.
                    atts[att_name] += 'px'
                style.append('%s: %s;' % (att_name, atts[att_name]))
                del atts[att_name]
        if style:
            atts['style'] = ' '.join(style)
        if (isinstance(node.parent, nodes.TextElement) or
            (isinstance(node.parent, nodes.reference) and
             not isinstance(node.parent.parent, nodes.TextElement))):
            # Inline context or surrounded by <a>...</a>.
            suffix = ''
        else:
            suffix = '\n'
        if 'align' in node:
            atts['class'] = 'align-%s' % node['align']
        self.context.append('')
        if ext in ('.svg', '.swf'): # place in an object element,
            # do NOT use an empty tag: incorrect rendering in browsers
            self.body.append(self.starttag(node, 'object', suffix, **atts) +
                             node.get('alt', uri) + '</object>' + suffix)
        else:
            self.body.append(self.emptytag(node, 'img', suffix, **atts))

    def depart_image(self, node):
        self.body.append(self.context.pop())

    def visit_title(self, node):
        """Only 6 section levels are supported by HTML."""
        check_id = 0
        close_tag = '</p>\n'
        if isinstance(node.parent, nodes.topic):
            self.body.append(
                  self.starttag(node, 'p', '', CLASS='topic-title first'))
        elif isinstance(node.parent, nodes.sidebar):
            self.body.append(
                  self.starttag(node, 'p', '', CLASS='sidebar-title'))
        elif isinstance(node.parent, nodes.Admonition):
            self.body.append(
                  self.starttag(node, 'p', '', CLASS='admonition-title'))
        elif isinstance(node.parent, nodes.table):
            self.body.append(
                  self.starttag(node, 'caption', ''))
            close_tag = '</caption>\n'
        elif isinstance(node.parent, nodes.document):
            print "title: parent=document", node.astext(), "\n"
            self.body.append(self.starttag(node, 'h1', '', CLASS='title'))
            close_tag = '</h1>\n'
            self.in_document_title = len(self.body)
        else:
            assert isinstance(node.parent, nodes.section)
            if self.builder.config.kindlebuilder_ignore_top_heading:
                if self.section_level == 1:
                    raise nodes.SkipNode
                h_level = self.section_level - 1
            else:
                h_level = self.section_level
            self.headings.visit(h_level, node.astext())
            print "visit_title(%d): " % h_level, node.astext()

    def depart_title(self, node):
        pass
