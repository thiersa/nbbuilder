# -*- coding: utf-8 -*-
"""
    sphinxcontrib.nbbuilder
    =========================

    Sphinx extension to output Jupyter Notebook files.

    .. moduleauthor:: Ad Thiers <ad@datacomputing.nl>

    :copyright: Copyright 2016 by Ad Thiers.
    :license: BSD, see LICENSE.txt for details.
"""

from __future__ import (print_function, unicode_literals, absolute_import)

from sphinx.writers.text import STDINDENT
from .builders.nb import IPynbBuilder, SingleIPynbBuilder


def setup(app):
    app.require_sphinx('1.0')
    app.add_builder(IPynbBuilder)
    app.add_builder(SingleIPynbBuilder)
    app.add_config_value('ipynb_file_suffix', ".ipynb", False)
    """This is the file name suffix for Jupyter Notebook files"""
    app.add_config_value('ipynb_link_suffix', None, False)
    """The is the suffix used in internal links. By default, takes the same value as ipynb_file_suffix"""
    app.add_config_value('ipynb_file_transform', None, False)
    """Function to translate a docname to a filename. By default, returns docname + ipynb_file_suffix."""
    app.add_config_value('ipynb_link_transform', None, False)
    """Function to translate a docname to a (partial) URI. By default, returns docname + ipynb_link_suffix."""
    app.add_config_value('ipynb_indent', STDINDENT, False)
    app.add_config_value('ipynb_kernel', None, False)
    """This is the kernel for the Jupyter notebook."""
    app.add_config_value('ipynb_metadata', None, False)
    """The metadata for the Jupyter notebook."""
    app.add_config_value('ipynb_skip_other_lang', True, False)
    """Do not render code-blocks for languages other than the kernel."""
    app.add_config_value('ipynb_author', None, False)
    app.add_config_value('ipynb_extra_path', [], False)
    app.add_config_value('ipynb_static_path', ['_static'], False)


