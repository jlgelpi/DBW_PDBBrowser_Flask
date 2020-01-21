import os
import sys

from flask import Flask, render_template, session
from flask_mysqldb import MySQL

def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_pyfile('config.py', silent=False)
    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path, exist_ok=True)
        os.makedirs(os.path.join(app.instance_path, 'tmp'), exist_ok=True)
    except OSError as e:
        sys.exit(e)

    mysql = MySQL(app)
   
# Index page
    def globals():
        globals = {}
        globals['compTypeArray'] = {}
        cur = mysql.connection.cursor()
        cur.execute("SELECT * from comptype")
        for key, value in cur.fetchall():
            globals['compTypeArray'][key] = value
        globals['expClasseArray'] = {}        
        cur.execute("SELECT * from expClasse")
        for key, value in cur.fetchall():
            globals['expClasseArray'][key] = value
        return globals
        
    @app.route('/')
    def index():
        glob_vars = globals()
        if 'queryData' not in session:
            queryData = {
                'minRes' : '0.0',
                'maxRes' : 'Inf',
                'query' : ''
            } 
        else:
            queryData = session['queryData']
            
        return render_template(
            'index.html', 
            title='PDB-Browser, Python version v0.1',
            queryData=queryData,
            compTypeArray=glob_vars['compTypeArray'],
            expClasseArray=glob_vars['expClasseArray']
        )
# Search page
    @app.route('/search', methods=['GET', 'POST'])
    def search():
        return render_template(
            'error.html', 
            title='PDB-Browser, Python version v0.1',
            error_text='Search not yet implemented'
        )
    return app