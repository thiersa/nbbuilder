"""
    sphinx.writers.nb
    ~~~~~~~~~~~~~~~~~~~

    Custom docutils writer for IPython Notebooks.

    :copyright: Copyright 2007-2015 by the Sphinx team, see AUTHORS.
    :license: BSD, see LICENSE for details.
"""

from enum import Enum
import types
from nbformat import v4 as ipynb

import sys
import os
import os.path
import time
import re
from urllib.parse import urlparse

try:   # check for the Python Imaging Library
    import PIL.Image as Image
except ImportError:
    try:   # sometimes PIL modules are put in PYTHONPATH's root
        import Image
    except ImportError:
        Image = None

from docutils import nodes, writers, languages

from sphinx.locale import admonitionlabels, _

NL = '\n\n'   # Markdown newline

unicode = str

class DecoMeta(type):
    def __new__(mcs, name, bases, attrs):
        for attr_name, attr_value in attrs.items():
            if isinstance(attr_value, types.FunctionType):
                attrs[attr_name] = mcs.deco(attr_value)
        return super(DecoMeta, mcs).__new__(mcs, name, bases, attrs)

    @classmethod
    def deco(mcs, func):
        def wrapper(*args, **kwargs):
            print("Calling", func.__name__,)
            return func(*args, **kwargs)
        return wrapper


class ListTypes(Enum):
    none = 0
    bullet = 1
    enumerated = 2
    description = 3
    field = 4
    definition = 5


class IPynbWriter(writers.Writer):
    supported = ('ipynb',)
    """Formats this writer supports."""

    output = None
    """Final translated form of `document`."""

    # Add configuration settings for Jupyter Notebook flavours here.
    settings_spec = ('Jupyter Notebook-specific options.', None, ())

    settings_defaults = {}

    lang_attribute = 'lang'  # name changes to 'xml:lang' in XHTML 1.1

    def __init__(self, builder):
        writers.Writer.__init__(self)
        self.builder = builder
        self.translator_class = self.builder.translator_class or IPynbTranslator

    def translate(self):
        visitor = self.translator_class(self.document, self.builder)
        self.document.walkabout(visitor)
        self.output = visitor.astext()


class IPynbTranslator(nodes.GenericNodeVisitor):

    def __init__(self, document, builder):
        nodes.NodeVisitor.__init__(self, document)
        self.settings = settings = document.settings
        lcode = settings.language_code
        self.language = languages.get_language(lcode, document.reporter)
        self.builder = builder

        self.head = []
        self.body = []
        self.foot = []
        self.cells = [ipynb.new_markdown_cell()]
        self.in_document_title = 0

        self.section_level = 0
        self.context = []
        self.colspecs = []

        self.list_level = 0
        self.list_itemcount = []
        self.list_type = []

        # TODO docinfo items can go in a footer HTML element (store in self.foot).
        self._docinfo = {
            'title': '',
            'subtitle': '',
            'author': [],
            'date': '',
            'copyright': '',
            'version': '',
        }

        # Customise Markdown syntax here. Still need to add literal, term,
        # indent, problematic etc...
        self.defs = {
            'emphasis': ('*', '*'),  # Could also use ('_', '_')
            'problematic': ('\n\n', '\n\n'),
            'strong': ('**', '**'),  # Could also use ('__', '__')
            'subscript': ('<sub>', '</sub>'),
            'superscript': ('<sup>', '</sup>'),
        }

    # Utility methods

    def astext(self):
        """Return the final formatted document as a string."""

        authors = self.builder.config.ipynb_author or []
        title = self._docinfo.get('title', '')
        metadata = self.builder.metadata

        nb = ipynb.new_notebook()
        nb["metadata"].update(metadata)
        nb["cells"] = self.cells

        return ipynb.writes(nb)

    def deunicode(self, text):
        text = text.replace(u'\xa0', '\\ ')
        text = text.replace(u'\u2020', '\\(dg')
        return text

    def encode(self, text):
        """Encode special characters in `text` & return."""
        # @@@ A codec to do these and all other HTML entities would be nice.
        text = unicode(text)
        return text.translate({
            ord('&'): u'&amp;',
            ord('<'): u'&lt;',
            ord('"'): u'&quot;',
            ord('>'): u'&gt;',
            ord('@'): u'&#64;', # may thwart some address harvesters
            # TODO: convert non-breaking space only if needed?
            0xa0: u'&nbsp;'}) # non-breaking space

    def ensure_eol(self):
        """Ensure the last line in body is terminated by new line."""
        if self.body and self.body[-1] and self.body[-1][-1] != '\n':
            self.body.append('\n')

    def list_marker(self, node):
        kind = self.list_type[-1]
        if kind == ListTypes.bullet:
            marker = '- '
        elif kind == ListTypes.enumerated:
            marker = "%1d. " % (self.list_itemcount[-1] % 10)
        elif kind == ListTypes.definition:
            marker = "-- Description -- "
        elif kind == ListTypes.field:
            marker = "-- Field -- "
        elif kind == ListTypes.option:
            marker = "-- Option -- "
        else:
            raise ValueError("Illegal list type", kind)

        return marker

    def indent(self):
        return '  ' * self.list_level

    def flush(self):
        if self.body:
            self.cells[-1]['source'] = ''.join(self.body)
            self.body = []
        else:
            del self.cells[-1]    # no content, remove the cell

    def new_cell(self, cell_type):
        self.flush()

        if cell_type == "code":
            cell = ipynb.new_code_cell()
        elif cell_type == "markdown":
            cell = ipynb.new_markdown_cell()
        else:
            raise ValueError("Unknown cell type '%s'" % cell_type)
        self.cells.append(cell)


    def attval(self, text, whitespace=re.compile('[\n\r\t\v\f]')):
        """Cleanse, HTML encode, and return attribute value text."""
        return self.encode(whitespace.sub(' ', text))

    def starttag(self, node, tagname, suffix='\n', empty=False, **attributes):
        """
        Construct and return a start tag given a node (id & class attributes
        are extracted), tag name, and optional attributes.
        """
        tagname = tagname.lower()
        prefix = []
        atts = {name.lower(): value for (name, value) in attributes.items()}
        classes = []
        languages = []
        class_attr = atts.pop('class', [])
        if isinstance(class_attr, str):
            class_attr = class_attr.split()

        # unify class arguments and move language specification
        for cls in node.get('classes', []) + class_attr:
            if cls.startswith('language-'):
                languages.append(cls[9:])
            elif cls.strip() and cls not in classes:
                classes.append(cls)
        if languages:
            # attribute name is 'lang' in XHTML 1.0 but 'xml:lang' in 1.1
            atts[self.lang_attribute] = languages[0]
        if classes:
            atts['class'] = classes

        attlist = sorted(atts.items())
        parts = [tagname]
        for name, value in attlist:
            # value=None was used for boolean attributes without
            # value, but this isn't supported by XHTML.
            assert value is not None
            if isinstance(value, list):
                values = [unicode(v) for v in value]
                parts.append('%s="%s"' % (name.lower(),
                                          self.attval(' '.join(values))))
            else:
                parts.append('%s="%s"' % (name.lower(),
                                          self.attval(unicode(value))))
        if empty:
            infix = ' /'
        else:
            infix = ''
        return ''.join(prefix) + '<%s%s>' % (' '.join(parts), infix) + suffix

    def emptytag(self, node, tagname, suffix='\n', **attributes):
        """Construct and return an XML-compatible empty tag."""
        return self.starttag(node, tagname, suffix, empty=True, **attributes)
    # Node visitor methods

    def default_visit(self, node):
        """Override for generic, uniform traversals."""

        node_type = node.__class__.__name__
        if node_type not in _warned:
            self.document.reporter.warning(
                'The ' + node_type + ' element is not supported.'
            )
            _warned.add(node_type)
        raise nodes.SkipNode

    def default_departure(self, node):
        """Override for generic, uniform traversals."""
        pass

    def depart_document(self, node):
        self.flush()

    def visit_bullet_list(self, node):
        self.list_type.append(ListTypes.bullet)
        self.list_itemcount.append(0)
        self.list_level += 1

    def depart_bullet_list(self, node):
        self.list_type.pop()
        self.list_itemcount.pop()
        self.list_level -= 1

    def visit_enumerated_list(self, node):
        self.list_type.append(ListTypes.enumerated)
        self.list_itemcount.append(0)
        self.list_level += 1

    def depart_enumerated_list(self, node):
        self.list_type.pop()
        self.list_itemcount.pop()
        self.list_level -= 1

    def visit_definition_list(self, node):
        self.list_type.append(ListTypes.definition)
        self.list_itemcount.append(0)
        self.list_level += 1
        marker = '<dl>\n'
        self.body.append(marker)

    def depart_definition_list(self, node):
        marker = '</dl>\n'
        self.body.append(marker)
        self.list_type.pop()
        self.list_itemcount.pop()
        self.list_level -= 1

    def visit_option_list(self, node):
        self.list_type.append(ListTypes.option)
        self.list_itemcount.append(0)
        self.list_level += 1

    def depart_option_list(self, node):
        self.list_type.pop()
        self.list_itemcount.pop()
        self.list_level -= 1

    def visit_list_item(self, node):

        self.list_itemcount[-1] += 1
        level = self.list_level

        marker = self.list_marker(node)

        self.body.append('  ' * (level-1) + marker)

    def depart_list_item(self, node):
        self.body.append('\n')

    def visit_definition_list_item(self, node):

        self.list_itemcount[-1] += 1
        # pass class arguments, ids and names to definition term:
        node.children[0]['classes'] = (
            node.get('classes', []) + node.children[0].get('classes', []))
        node.children[0]['ids'] = (
            node.get('ids', []) + node.children[0].get('ids', []))
        node.children[0]['names'] = (
            node.get('names', []) + node.children[0].get('names', []))

    def depart_definition_list_item(self, node):
        self.body.append('\n')

    def visit_definition(self, node):
        self.body.append(
            self.starttag(node, 'dd'))

    def depart_definition(self, node):
        self.body.append('</dd>\n')

    def visit_term(self, node):
        self.body.append(
            self.starttag(node, 'dt', ''))

    def depart_term(self, node):
        self.body.append('</dt>\n')

    def visit_field(self, node):
        self.body.append(
            self.starttag(node, 'tr', ''))

    def depart_field(self, node):
        self.body.append('</tr>\n')

    def visit_field_body(self, node):
        self.body.append(
            self.starttag(node, 'td', ''))

    def depart_field_body(self, node):
        self.body.append('</td>\n')

    def visit_field_list(self, node):
        self.body.append(
            self.starttag(node, 'table', '', frame='void', rules='none'))
        self.body.append(
            self.starttag(node, 'tbody', valign='top'))

    def depart_field_list(self, node):
        self.body.append('</tbody></table>\n')

    def visit_field_name(self, node):

        self.body.append(
            self.starttag(node, 'th', ''))

    def depart_field_name(self, node):
        self.body.append(':</th>')

    def visit_figure(self, node):
        atts = {}

        classes = ['figure']
        if node.get('align'):
            classes.append("align-" + node['align'])
        atts['class'] = classes

        if node.get('width'):
            atts['style'] = 'width: %s' % node['width']

        self.body.append(
            self.starttag(node, 'div', '', **atts))

    def depart_figure(self, node):
        self.body.append('</div>\n')

    # Image types to place in an <object> element
    # SVG not supported by IE up to version 8
    # (html4css1 strives for IE6 compatibility)
    object_image_types = {#'.svg': 'image/svg+xml',
                         '.swf': 'application/x-shockwave-flash'}

    def visit_image(self, node):
        atts = {}
        uri = node['uri']
        print('uri: "%s"' % uri)
        ext = os.path.splitext(uri)[1].lower()
        if ext == '.*':
            ext = '.svg'  # assume .svg
            uri = uri.replace('.*', ext)

        if ext in self.object_image_types:
            atts['data'] = uri
            atts['type'] = self.object_image_types[ext]
        else:
            atts['src'] = uri
            atts['alt'] = node.get('alt', uri)
        # image size
        if 'width' in node:
            atts['width'] = node['width']
        if 'height' in node:
            atts['height'] = node['height']
        if 'scale' in node:
            if (Image and not ('width' in node and 'height' in node)
                and self.settings.file_insertion_enabled):
                imagepath = urlparse(uri).path
                try:
                    img = Image.open(
                            imagepath.encode(sys.getfilesystemencoding()))
                except (IOError, UnicodeEncodeError):
                    pass # TODO: warn?
                else:
                    self.settings.record_dependencies.add(
                        imagepath.replace('\\', '/'))
                    if 'width' not in atts:
                        atts['width'] = '%dpx' % img.size[0]
                    if 'height' not in atts:
                        atts['height'] = '%dpx' % img.size[1]
                    del img
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
        if ext in self.object_image_types: # ('.svg', '.swf')
            # do NOT use an empty tag: incorrect rendering in browsers
            self.body.append(self.starttag(node, 'object', suffix, **atts) +
                             node.get('alt', uri) + '</object>' + suffix)
        else:
            self.body.append(self.emptytag(node, 'img', suffix, **atts))

    def depart_image(self, node):
        # self.body.append(self.context.pop())
        pass

    def visit_compound(self, node):
        pass

    def visit_start_of_file(self, node):
        pass

    def visit_raw(self, node):
        if 'html' in node.get('format', '').split():
            t = isinstance(node.parent, nodes.TextElement) and 'span' or 'div'
            if node['classes']:
                self.body.append(self.starttag(node, t, suffix=''))
            self.body.append(node.astext())
            if node['classes']:
                self.body.append('</%s>' % t)
        # Keep non-HTML raw text out of output:
        raise nodes.SkipNode

    def visit_topic(self, node):
        self.body.append(self.starttag(node, 'div', CLASS='topic'))
        self.topic_classes = node['classes']
        # TODO: replace with ::
        #   self.in_contents = 'contents' in node['classes']

    def depart_topic(self, node):
        self.body.append('</div>\n')
        self.topic_classes = []
        # TODO self.in_contents = False

    def visit_rubric(self, node):
        self.body.append(self.starttag(node, 'p', '', CLASS='rubric'))

    def depart_rubric(self, node):
        self.body.append('</p>\n')

    def visit_target(self, node):
        if not ('refuri' in node or 'refid' in node
                or 'refname' in node):
            self.body.append(self.starttag(node, 'span', '', CLASS='target'))
            self.context.append('</span>')
        else:
            self.context.append('')

    def depart_target(self, node):
        self.body.append(self.context.pop())

    def visit_literal_strong(self, node):
        return self.visit_strong(node)

    def depart_literal_strong(self, node):
        return self.depart_strong(node)

    def visit_literal_block(self, node):
        lang = node.get('language', '')
        classes = node.get('classes', [])
        if 'code-cell' in classes:
            if not lang or lang == self.builder.kernel:
                self.new_cell('code')
                self.body.append(node.astext())
                self.new_cell('markdown')
                raise nodes.SkipNode
            elif self.builder.skip_other_lang:
                raise nodes.SkipNode
            else:
                self.body.append('##### code-block for %s\n\n' % lang)

        self.body.append(self.indent() + "``` %s\n" % lang)
        self.body.append(node.astext())
        self.body.append("```\n")
        raise nodes.SkipNode

    def depart_literal_block(self, node):
        pass

    def visit_Text(self, node):
        self.body.append(node.astext())
        raise nodes.SkipNode

    def visit_comment(self, node):
        self.body.append('<!-- ' + node.astext() + ' -->\n')
        raise nodes.SkipNode

    def visit_docinfo_item(self, node, name):
        if name == 'author':
            self._docinfo[name].append(node.astext())
        else:
            self._docinfo[name] = node.astext()
        raise nodes.SkipNode

    def visit_document(self, node):
        pass

    def visit_emphasis(self, node):
        self.body.append(self.defs['emphasis'][0])

    def depart_emphasis(self, node):
        self.body.append(self.defs['emphasis'][1])

    def visit_paragraph(self, node):
        if not isinstance(node.parent, nodes.list_item):
            self.ensure_eol()
            self.body.append('\n' + self.indent())

    def depart_paragraph(self, node):
        self.body.append('\n')

    def visit_problematic(self, node):
        self.body.append(self.defs['problematic'][0])

    def depart_problematic(self, node):
        self.body.append(self.defs['problematic'][1])

    def visit_section(self, node):
        self.section_level += 1

    def depart_section(self, node):
        self.section_level -= 1

    def visit_strong(self, node):
        self.body.append(self.defs['strong'][0])

    def depart_strong(self, node):
        self.body.append(self.defs['strong'][1])

    def visit_subscript(self, node):
        self.body.append(self.defs['subscript'][0])

    def depart_subscript(self, node):
        self.body.append(self.defs['subscript'][1])

    def visit_subtitle(self, node):
        if isinstance(node.parent, nodes.document):
            self.visit_docinfo_item(node, 'subtitle')
            raise nodes.SkipNode

    def visit_superscript(self, node):
        self.body.append(self.defs['superscript'][0])

    def depart_superscript(self, node):
        self.body.append(self.defs['superscript'][1])

    def visit_system_message(self, node):
        # TODO add report_level
        # if node['level'] < self.document.reporter['writer'].report_level:
        #    Level is too low to display:
        #    raise nodes.SkipNode
        attr = {}
        if node.hasattr('id'):
            attr['name'] = node['id']
        if node.hasattr('line'):
            line = ', line %s' % node['line']
        else:
            line = ''
        self.body.append('"System Message: %s/%s (%s:%s)"\n'
                         % (node['type'], node['level'], node['source'], line))

    def visit_title(self, node):
        self.body.append('\n' + self.section_level * '#' + ' ')
        if self.section_level <= 1 and not self.in_document_title:
            self.in_document_title = len(self.body)

    def depart_title(self, node):
        self.body.append('\n')
        if self.in_document_title > 0:
            self._docinfo['title'] = ''.join(self.body[self.in_document_title:-1])
            self.in_document_title = -1

    def visit_transition(self, node):
        # Simply replace a transition by a horizontal rule.
        # Could use three or more '*', '_' or '-'.
        self.body.append('\n---\n\n')
        raise nodes.SkipNode

    def visit_table(self, node):
        self.body.append(
            self.starttag(node, 'table', '', border='1'))
       # elf.body.append('<table border="1">')

    def depart_table(self, node):
        self.body.append('</table>\n')

    def visit_tgroup(self, node):
        pass

    def depart_tgroup(self, node):
        pass

    def visit_row(self, node):
        self.body.append(
            self.starttag(node, 'tr', ''))
        node.column = 0

    def depart_row(self, node):
        self.body.append('</tr>\n')

    def visit_thead(self, node):
        self.body.append(
            self.starttag(node, 'thead', '', valign='bottom'))

    def depart_thead(self, node):
        self.body.append('</thead>\n')

    def visit_entry(self, node):
        atts = {}

        if isinstance(node.parent.parent, nodes.thead):
            tagname = 'th'
        else:
            tagname = 'td'
        node.parent.column += 1

        self.body.append('<%s ' % tagname)
        if 'morerows' in node:
            atts['rowspan'] = '%d' % (node['morerows'] + 1)

        if 'morecols' in node:
            atts['colspan'] = '%d' % (node['morecols'] + 1)
            node.parent.column += node['morecols']

        self.body.append(
            self.starttag(node, tagname, '', atts))

        self.context.append('</%s>\n' % tagname)
        if len(node) == 0:              # empty cell
            self.body.append('&nbsp;')

    def depart_entry(self, node):
        self.body.append(self.context.pop())

    def visit_tbody(self, node):
        self.body.append(
            self.starttag(node, 'tbody', '', valign='top'))

    def depart_tbody(self, node):
        self.body.append('</tbody>\n')

    def visit_colspec(self, node):
        raise nodes.SkipNode

    def depart_colspec(self, node):
        pass

    def visit_literal(self, node):
        self.body.append('`')

    def depart_literal(self, node):
        self.body.append('`')

    def visit_container(self, node):
        pass

    def depart_container(self, node):
        pass

    def visit_caption(self, node):
        if isinstance(node.parent, nodes.container) and node.parent.get('literal_block'):
            self.body.append(
                self.starttag(node, 'div', '', CLASS='code-block-caption'))
        else:
            pass
            # nodes.GenericNodeVisitor.visit_caption(self, node)
        # self.add_fignumber(node.parent)
        self.body.append(
            self.starttag(node, 'span', '', CLASS='caption-text'))

    def depart_caption(self, node):
        self.body.append('</span>')

    def visit_admonition(self, node):
        pass

    def depart_admonition(self, node):
        pass

    def _make_visit_admonition(name):
        def visit_admonition(self, node):
            if isinstance(node.children[0], nodes.Sequential):
                self.body.append(NL)

            self.body.append('\n<table><tr><th>%s</th></tr><tr><td>\n' %
                             admonitionlabels[name])

        return visit_admonition

    def _depart_admonition(self, node):
        self.body.append('\n</td></tr></table>\n')

    visit_attention = _make_visit_admonition('attention')
    depart_attention = _depart_admonition
    visit_caution = _make_visit_admonition('caution')
    depart_caution = _depart_admonition
    visit_danger = _make_visit_admonition('danger')
    depart_danger = _depart_admonition
    visit_error = _make_visit_admonition('error')
    depart_error = _depart_admonition
    visit_hint = _make_visit_admonition('hint')
    depart_hint = _depart_admonition
    visit_important = _make_visit_admonition('important')
    depart_important = _depart_admonition
    visit_note = _make_visit_admonition('note')
    depart_note = _depart_admonition
    visit_tip = _make_visit_admonition('tip')
    depart_tip = _depart_admonition
    visit_warning = _make_visit_admonition('warning')
    depart_warning = _depart_admonition
    visit_seealso = _make_visit_admonition('seealso')
    depart_seealso = _depart_admonition

    def visit_compact_paragraph(self, node):
        self.body.append(self.indent())

    def visit_title_reference(self, node):
        self.body.append('*')

    def depart_title_reference(self, node):
        self.body.append('*')

    def visit_reference(self, node):
        pass

    def depart_reference(self, node):
        pass

    def visit_block_quote(self, node):
        self.body.append(self.indent())

    def depart_block_quote(self, node):
        pass

    def visit_doctest_block(self, node):
        self.body.append(self.indent() + '``` python\n')
        self.body.append(node.astext().replace('<BLANKLINE>\n',
                                               '\n'))
        self.body.append('```\n')
        raise nodes.SkipNode

    def depart_doctest_block(self, node):
        pass

    def visit_inline(self, node):
        pass

    def depart_inline(self, node):
        pass

    def visit_math(self, node):
        self.body.append('$' + node['latex'] + '$')
        raise nodes.SkipNode

    def visit_math_block(self, node):
        self.body.append('\n' + self.indent() +
                         '$$' + node['latex'] + '$$\n')
        raise nodes.SkipNode

    def visit_displaymath(self, node):
        self.body.append('\n' + self.indent() +
                         '$$' + node['latex'] + '$$\n')
        raise nodes.SkipNode

# TODO Eventually we should silently ignore unsupported reStructuredText
#      constructs and document somewhere that they are not supported.
#     In the meantime raise a warning *once* for each unsupported element.
_warned = set()