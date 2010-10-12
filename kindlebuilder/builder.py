# encoding: utf-8

import os
import codecs

from docutils import nodes
from docutils.io import DocTreeInput, StringOutput
from docutils.frontend import OptionParser

import sphinx.builders
import sphinx.theming

from sphinx.highlighting import PygmentsBridge
from sphinx.locale import admonitionlabels, versionlabels, _
from sphinx.util.console import bold, darkgreen, brown
from sphinx.writers.html import HTMLTranslator

from sphinx.util.nodes import inline_all_toctrees
from sphinx.util.osutil import SEP, os_path, relative_uri, ensuredir, \
     movefile, ustrftime, copyfile
from sphinx import __version__

import kindlewriter
import mobi_generator


class KindleBuilder(sphinx.builders.Builder):
    name = 'kindle'
    format = 'html'
    copysource = False
    out_suffix = '.html'
    link_suffix = '.html'
    
    def init(self):
        self.init_highlighter()
        self.output = None
     
    def init_highlighter(self):
        self.highlighter = PygmentsBridge('html', 'sphinx',
                                          self.config.trim_doctest_flags)
    
    def get_outdated_docs(self):
        return 'all documents'

    def assemble_doctree(self):
        master = self.config.master_doc
        tree = self.env.get_doctree(master)
        tree = inline_all_toctrees(self, set(), master, tree, darkgreen)
        tree['docname'] = master
        self.env.resolve_references(tree, master, self)
        self.fix_refuris(tree)
        return tree

    def fix_refuris(self, tree):
        # fix refuris with double anchor
        fname = self.config.master_doc + self.out_suffix
        for refnode in tree.traverse(nodes.reference):
            if 'refuri' not in refnode:
                continue
            refuri = refnode['refuri']
            hashindex = refuri.find('#')
            if hashindex < 0:
                continue
            hashindex = refuri.find('#', hashindex+1)
            if hashindex >= 0:
                refnode['refuri'] = fname + refuri[hashindex:]

    def prepare_writing(self, docnames):
        from sphinx.search import IndexBuilder
        self.docwriter = kindlewriter.KindleHTMLWriter(self)
        self.docsettings = OptionParser(
            defaults=self.env.settings,
            components=(self.docwriter,)).get_default_values()
        self.docsettings.compact_lists = True
        
        # determine the additional indices to include
        self.domain_indices = []

        # html_domain_indices can be False/True or a list of index names
        indices_config = self.config.html_domain_indices
        if indices_config:
            for domain in self.env.domains.itervalues():
                for indexcls in domain.indices:
                    indexname = '%s-%s' % (domain.name, indexcls.name)
                    if isinstance(indices_config, list):
                        if indexname not in indices_config:
                            continue
                    # deprecated config value
                    if indexname == 'py-modindex' and \
                           not self.config.html_use_modindex:
                        continue
                    content, collapse = indexcls(domain).generate()
                    if content:
                        self.domain_indices.append(
                            (indexname, indexcls, content, collapse))

        lufmt = self.config.html_last_updated_fmt
        if lufmt is not None:
            self.last_updated = ustrftime(lufmt or _('%b %d, %Y'))
        else:
            self.last_updated = None

        self.relations = self.env.collect_relations()

        rellinks = []
        if self.config.html_use_index:
            rellinks.append(('genindex', _('General Index'), 'I', _('index')))
        for indexname, indexcls, content, collapse in self.domain_indices:
            # if it has a short name
            if indexcls.shortname:
                rellinks.append((indexname, indexcls.localname,
                                 '', indexcls.shortname))

        self.globalcontext = dict(
            project = self.config.project,
            release = self.config.release,
            version = self.config.version,
            last_updated = self.last_updated,
            copyright = self.config.copyright,
            master_doc = self.config.master_doc,
            docstitle = self.config.html_title,
            shorttitle = self.config.html_short_title,
            show_copyright = self.config.html_show_copyright,
            show_sphinx = self.config.html_show_sphinx,
            file_suffix = self.out_suffix,
            sphinx_version = __version__,
            rellinks = rellinks,
            builder = self.name,
        )

    def write(self, *ignored):
        docnames = self.env.all_docs

        self.info(bold('preparing documents... '), nonl=True)
        self.prepare_writing(docnames)
        self.info('done')

        self.info(bold('assembling single document... '), nonl=True)
        doctree = self.assemble_doctree()
        self.info()
        self.info(bold('writing... '), nonl=True)
        self.write_doc(self.config.master_doc, doctree)
        self.info('done')

    def write_doc(self, docname, doctree):
        """Write one document file.
        This method is overwritten in order to fix fragment identifiers
        and to add visible external links.
        """
        #self.fix_ids(doctree)
        #self.add_visible_links(doctree)
        
        destination = StringOutput(encoding='utf-8')
        doctree.settings = self.docsettings

        self.secnumbers = self.env.toc_secnumbers.get(docname, {})
        self.imgpath = relative_uri(self.get_target_uri(docname), '_images')
        self.post_process_images(doctree)
        self.dlpath = relative_uri(self.get_target_uri(docname), '_downloads')
        self.docwriter.write(doctree, destination)
        self.docwriter.assemble_parts()
        body = self.docwriter.parts['fragment']
        self.handle_page(docname, self.docwriter.parts, event_arg=doctree)

    def get_target_uri(self, docname, typ=None):
        if docname in self.env.all_docs:
            # all references are on the same page...
            return self.config.master_doc + self.out_suffix + \
                   '#document-' + docname
        else:
            # chances are this is a html_additional_page
            return docname + self.out_suffix

    def handle_page(self, pagename, part, event_arg=None):
        ctx = self.globalcontext.copy()
        ctx['body'] = part['fragment']
        ctx['encoding'] = encoding = self.config.html_output_encoding
        
        templatename='default'
        outfilename=None, 

        self.app.emit('html-page-context', pagename, templatename,
                      ctx, event_arg)
        self.output = part['whole_contents']
        # for debug
        def get_outfilename(pagename):
            return os.path.join(self.outdir, os_path(pagename) + self.out_suffix)

        outfilename = get_outfilename('index')
        # outfilename's path is in general different from self.outdir
        ensuredir(os.path.dirname(outfilename))
        try:
            f = codecs.open(outfilename, 'w', encoding)
            try:
                f.write(self.output)
            finally:
                f.close()
        except (IOError, OSError), err:
            self.warn("error writing file %s: %s" % (outfilename, err))

    def finish(self):
        self.info(bold('writing additional files...'), nonl=1)

        # pages from extensions
        for pagelist in self.app.emit('html-collect-pages'):
            for pagename, context, template in pagelist:
                self.handle_page(pagename, context, template)

        # the global general index
        #if self.config.html_use_index:
        #    self.write_genindex()

        # the global domain-specific indices
        #self.write_domain_indices()
        
        self.info()

        #self.copy_image_files()
        #self.copy_download_files()
        #self.copy_static_files()
        #self.write_buildinfo()
        
        if self.config.kindlebuilder_title:
            name = self.config.kindlebuilder_title
        else:
            name = "%s v%s documentation" % (self.config.project, self.config.version)

        generator = mobi_generator.MobiFileGenerator()
        generator.set_name(name)
        generator.set_text(self.output)
        print len(self.docwriter.images)
        generator.set_images(self.docwriter.images)
        generator.set_cover_image(self.config.kindlebuilder_cover_image)
        generator.generate(self.outdir, self.config.kindlebuilder_basename)
