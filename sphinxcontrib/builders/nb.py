# -*- coding: utf-8 -*-
"""
    sphinx.builders.nb
    ~~~~~~~~~~~~~~~~~~~~

    IPython Notebook Sphinx builder.

    :copyright: Copyright 2007-2015 by the Sphinx team, see AUTHORS.
    :license: BSD, see LICENSE for details.
"""

import codecs
from os import path

from six import iteritems

from docutils import nodes
from docutils.io import StringOutput
from sphinx import builders

from sphinx.util.osutil import ensuredir, os_path
from sphinx.util.nodes import inline_all_toctrees
from sphinx.util.console import bold, darkgreen


from ..writers.nb import IPynbWriter

NB_METADATA = {
    'python': {
        "kernelspec": {
            "display_name": "Python",
            "language": "python",
            "name": "Python"
        },
        "language_info": {
            "codemirror_mode": {
                "name": "ipython",
                "version": 3
            },
            "file_extension": ".py",
            "mimetype": "text/x-python",
            "name": "python",
            "nbconvert_exporter": "python",
            "pygments_lexer": "ipython3",
            "version": "3.5.2"
        }
    },
    'R': {
        "kernelspec": {
            "display_name": "R",
            "language": "R",
            "name": "ir"
        },
        "language_info": {
            "codemirror_mode": "r",
            "file_extension": ".r",
            "mimetype": "text/x-r-source",
            "name": "R",
            "pygments_lexer": "r",
            "version": "3.2.3"
        }
    },
    'julia': {
        "kernelspec": {
            "display_name": "Julia 0.4.4-pre",
            "language": "julia",
            "name": "julia-0.4"
        },
        "language_info": {
            "file_extension": ".jl",
            "mimetype": "application/julia",
            "name": "julia",
            "version": "0.4.4"
        }
    },
    'ruby': {
        "kernelspec": {
            "display_name": "Ruby 2.2.1",
            "language": "ruby",
            "name": "ruby"
        },
        "language_info": {
            "file_extension": ".rb",
            "mimetype": "application/x-ruby",
            "name": "ruby",
            "version": "2.2.1"
        }
    }
}


class IPynbBuilder(builders.Builder):
    """
    Builds standalone Jupyter Notebooks.
    """

    name = 'ipynb'
    format = 'ipynb'
    out_suffix = '.ipynb'
    allow_parallel = True

    def init(self):
        pass

    def get_outdated_docs(self):
        for docname in self.env.found_docs:
            if docname not in self.env.all_docs:
                yield docname
                continue
            targetname = self.env.doc2path(docname, self.outdir,
                                           self.out_suffix)
            try:
                targetmtime = path.getmtime(targetname)
            except Exception:
                targetmtime = 0
            try:
                srcmtime = path.getmtime(self.env.doc2path(docname))
                if srcmtime > targetmtime:
                    yield docname
            except EnvironmentError:
                # source doesn't exist anymore
                pass

    def get_target_uri(self, docname, typ=None):
        return ''

    def prepare_writing(self, docnames):
        self.writer = IPynbWriter(self)
        metadata = self.config.ipynb_metadata

        if metadata:
            self.metadata = metadata.copy()
            try:
                self.kernel = metadata['kernelspec']['language']
            except KeyError:
                raise ValueError('No such kernel %s' %
                                 self.kernel, *NB_METADATA)
            if self.config.ipynb_kernel and self.config.ipynb_kernel != kernel:
                self.warn(
                    'The kernel "%s" and metaclass[kernelspec"]["language"]'
                    ' "%s" are incompatible' %
                    (self.kernel, metadata['kernelspec']['language']))
        else:
            self.kernel = self.config.ipynb_kernel or 'python'
            try:
                self.metadata = NB_METADATA[self.kernel].copy()
            except KeyError:
                raise ValueError('No metadata for kernel "%s"' % self.kernel,
                                 *NB_METADATA)
            self.metadata["author"] = self.config.ipynb_author

        self.skip_other_lang = self.config.ipynb_skip_other_lang

    def write_doc(self, docname, doctree):
        self.current_docname = docname
        destination = StringOutput(encoding='utf-8')
        self.info(bold('writing doc... '), nonl=True)
        self.info(docname)
        self.writer.write(doctree, destination)
        outfilename = path.join(self.outdir, os_path(docname) + self.out_suffix)
        ensuredir(path.dirname(outfilename))
        try:
            f = codecs.open(outfilename, 'w', 'utf-8')
            try:
                f.write(self.writer.output)
            finally:
                f.close()
        except (IOError, OSError) as err:
            self.warn("error writing file %s: %s" % (outfilename, err))

    def finish(self):
        pass


class SingleIPynbBuilder(IPynbBuilder):
    """
    A IPynbBuilder subclass that puts the whole document tree on one
    Jupyter Notebook.
    """

    name = 'singleipynb'

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

    def assemble_doctree(self):
        master = self.config.master_doc
        tree = self.env.get_doctree(master)

        tree = inline_all_toctrees(self, set(), master, tree, darkgreen, [master])
        tree['docname'] = master

        # self.env.resolve_references(tree, master, self)
        # self.fix_refuris(tree)

        return tree

    def write(self, *ignored):
        docnames = self.env.all_docs

        self.info(bold('preparing documents... '), nonl=True)
        self.prepare_writing(docnames)
        self.info('done')

        self.info(bold('assembling single document... '), nonl=True)
        doctree = self.assemble_doctree()
        # self.env.toc_secnumbers = self.assemble_toc_secnumbers()
        # self.env.toc_fignumbers = self.assemble_toc_fignumbers()
        self.info()
        self.info(bold('writing... '), nonl=True)
        self.write_doc_serialized(self.config.master_doc, doctree)
        self.write_doc(self.config.master_doc, doctree)
        self.info('done')

    def assemble_toc_secnumbers(self):
        # Assemble toc_secnumbers to resolve section numbers on SingleHTML.
        # Merge all secnumbers to single secnumber.
        #
        # Note: current Sphinx has refid confliction in singlehtml mode.
        #       To avoid the problem, it replaces key of secnumbers to
        #       tuple of docname and refid.
        #
        #       There are related codes in inline_all_toctres() and
        #       HTMLTranslter#add_secnumber().
        new_secnumbers = {}
        for docname, secnums in iteritems(self.env.toc_secnumbers):
            for id, secnum in iteritems(secnums):
                new_secnumbers[(docname, id)] = secnum

        return {self.config.master_doc: new_secnumbers}

    def assemble_toc_fignumbers(self):
        # Assemble toc_fignumbers to resolve figure numbers on SingleHTML.
        # Merge all fignumbers to single fignumber.
        #
        # Note: current Sphinx has refid confliction in singlehtml mode.
        #       To avoid the problem, it replaces key of secnumbers to
        #       tuple of docname and refid.
        #
        #       There are related codes in inline_all_toctres() and
        #       HTMLTranslter#add_fignumber().
        new_fignumbers = {}
        # {u'foo': {'figure': {'id2': (2,), 'id1': (1,)}}, u'bar': {'figure': {'id1': (3,)}}}
        for docname, fignumlist in iteritems(self.env.toc_fignumbers):
            for figtype, fignums in iteritems(fignumlist):
                new_fignumbers.setdefault((docname, figtype), {})
                for id, fignum in iteritems(fignums):
                    new_fignumbers[(docname, figtype)][id] = fignum

        return {self.config.master_doc: new_fignumbers}

