import os
import re
import time
import codecs
from os import path

from docutils import nodes

from sphinx import addnodes

import builder


_refuri_re = re.compile("([^#:]*#)(.*)")


def setup(app):
    theme_path = os.path.join(os.path.dirname(__file__), "kindle")
    app.add_config_value("kindlebuilder_basename", "default", "")
    app.add_config_value("kindlebuilder_title", "", "")
    app.add_config_value("kindlebuilder_cover_image", None, "")
    app.add_config_value("kindlebuilder_ignore_top_heading", True, "html")
    app.add_builder(builder.KindleBuilder)
