#!/bin/tcsh
source venv/bin/activate.csh
setenv FLASK_APP pdb_browser
setenv FLASK_ENV development
setenv FLASK_RUN_PORT 5001
flask run
