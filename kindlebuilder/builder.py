# encoding: utf-8

import sphinx.builders
import sphinx.theming
from sphinx.util.nodes import inline_all_toctrees
from sphinx.writers.html import HTMLTranslator
from sphinx.highlighting import PygmentsBridge
from sphinx.util.console import bold, darkgreen, brown

from sphinx import __version__

import kindlewriter


class KindleBuilder(sphinx.builders.Builder):
    name = 'kindle'
    format = 'html'
    copysource = False
    out_suffix = '.html'
    link_suffix = '.html'
    
    def init(self):
        self.init_highlighter()
        self.init_translator_class()
     
    def init_highlighter(self):
        self.highlighter = PygmentsBridge('html', 'sphinx',
                                          self.config.trim_doctest_flags)

    def init_translator_class(self):
        self.translator_class = HTMLTranslator
    
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

    def prepare_writing(self, docnames):
        from sphinx.search import IndexBuilder
        print "prepare_writing"
        self.docwriter = kindlewriter.KindleHTMLWriter(self)

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
            embedded = self.embedded,
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
        metatags = self.docwriter.clean_meta

        ctx = self.get_doc_context(docname, body, metatags)
        self.index_page(docname, doctree, ctx.get('title', ''))
        self.handle_page(docname, ctx, event_arg=doctree)
 