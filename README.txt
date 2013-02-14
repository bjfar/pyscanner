I am in the middle of building this package according to the guidelines at http://guide.python-distribute.org/creation.html

The README.txt file should be written in reST so that the PyPI can use it to generate your project’s PyPI page. Here’s a 10-second intro to reST that you might use to start with:

===========
Towel Stuff
===========

Towel Stuff provides such and such and so and so. You might find
it most useful for tasks involving <x> and also <y>. Typical usage
often looks like this::

    #!/usr/bin/env python

    from towelstuff import location
    from towelstuff import utils

    if utils.has_towel():
        print "Your towel is located:", location.where_is_my_towel()

(Note the double-colon and 4-space indent formatting above.)

Paragraphs are separated by blank lines. *Italics*, **bold**,
and ``monospace`` look like this.


A Section
=========

Lists look like this:

* First

* Second. Can be multiple lines
  but must be indented properly.

A Sub-Section
-------------

Numbered lists look like you'd expect:

1. hi there

2. must be going

Urls are http://like.this and links can be
written `like this <http://www.example.com/foo/bar>`_.
