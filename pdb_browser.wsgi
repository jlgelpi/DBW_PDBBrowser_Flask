#! /usr/bin/python 
activate_this = 'path_to_venv/bin/activate_this.py'
with open (activate_this) as file_:
    exec(file_.read(), dict(__file__=activate_this))

import logging
import sys
logging.basicConfig(stream=sys.stderr)
sys.path.insert(0, 'path_to_py_pdb_browser')
from pdb_browser import create_app
application = create_app()

