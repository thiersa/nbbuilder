.. -*- restructuredtext -*-

=======================
README for NB Builder
=======================

Sphinx_ extension to build NB (IPynb_) files.

Requirements
============

* Sphinx_ 1.0 or later
* Python 2.6 or later

Installing
==========

Using pip
---------

    pip install sphinxcontrib-nbbuilder

Manual
------

    hg clone http://bitbucket.org/birkenfeld/sphinx-contrib
    cd sphinx-contrib/nbbuilder
    python setup.py install

If you want to take a look and have a try, you can put the IPynb builder in
an extension subdirectory, and adjust ``sys.path`` to tell Sphinx where to
look for it:

- Add the extensions directory to the path in ``conf.py``. E.g.

    sys.path.append(os.path.abspath('exts'))

Usage
=====

- Set the builder as a extension in ``conf.py``:

    extensions = ['sphinxcontrib.nbbuilder']

- Run sphinx-build with target ``ipynb``:

    sphinx-build -b ipynb -c . build/ipynb

Configuration
=============

The following four configuration variables are defined by sphinxcontrib.nbbuilder:

.. confval:: ipynb_file_suffix

   This is the file name suffix for generated Jupyter Notebook files.
   The default is
   ``".ipynb"``.

.. confval:: ipynb_link_suffix

   Suffix for generated links to Jupyter Notebook files.
   The default is whatever
   :confval:`ipynb_file_suffix` is set to.

.. confval:: ipynb_file_transform

   Function to translate a docname to a filename. 
   By default, returns `docname` + :confval:`ipynb_file_suffix`.

.. confval:: ipynb_link_transform

   Function to translate a docname to a (partial) URI. 
   By default, returns `docname` + :confval:`ipynb_link_suffix`.


Further Reading
===============

.. _Sphinx: http://sphinx-doc.org/
.. _`sphinx-contrib`: http://bitbucket.org/birkenfeld/sphinx-contrib
.. _reStructuredText: http://docutils.sourceforge.net/rst.html
.. _IPynb: https://nbformat.readthedocs.io/

Feedback
========

The IPynb builder is in a preliminary state. It's not (yet) widely used, so
any feedback is particularly welcome.
