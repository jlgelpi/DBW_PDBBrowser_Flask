import os
import sys

from flask import Flask, render_template, session, request, url_for, redirect
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
   
#
# Global data
#
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
        globals['expTypeArray'] = {}        
        cur.execute("SELECT idExptype, ExpType from expType")
        for key, value in cur.fetchall():
            globals['expTypeArray'][key] = value
        return globals

#
# Index 
#

    @app.route('/')
    def index():
        glob_vars = globals()
        if 'query_data' not in session:
            query_data = {
                'minRes' : '0.0',
                'maxRes' : 'Inf',
                'query' : ''
            } 
        else:
            query_data = session['query_data']
            
        return render_template(
            'index.html', 
            title=app.config['TITLE'],
            query_data=query_data,
            compTypeArray=glob_vars['compTypeArray'],
            expClasseArray=glob_vars['expClasseArray']
        )
#
# Search page
#
    @app.route('/search/', methods=['GET', 'POST'])
    def search():
        session['query_data'] = request.form
        #PDB ID 
        if request.form['idCode']:
            return redirect(url_for('show', idCode=request.form['idCode']))
        else:
        # Blast
        # Search
        
            return request.form

#
# Show Structure
#
    @app.route('/show/<idCode>')
    def show(idCode):
        glob_vars = globals()
        cur = mysql.connection.cursor()
        rs = cur.execute("SELECT e.* from entry e where e.idCode='{}'".format(idCode))
        columns = [col[0] for col in cur.description]
        data = dict(zip(columns, cur.fetchone()))
        rs = cur.execute("SELECT a.author from author a, author_has_entry ae where ae.idCode='{}' and a.idAuthor = ae.idAuthor order by a.author".format(idCode))
        data['author_list'] = ', '.join([aut[0] for aut in cur.fetchall()])
        rs = cur.execute("SELECT s.source from source s, entry_has_source es where es.idCode='{}' and s.idSource = es.idSource order by s.source".format(idCode))
        data['source_list'] = ', '.join([sc[0] for sc in cur.fetchall()])
        rs = cur.execute("SELECT * from sequence s where s.idCode='{}' order by s.chain".format(idCode))
        data['sequences'] = []
        for sq in cur.fetchall():
            fasta = ">{}\n{}".format(sq[3], sq[2])
            data['sequences'].append(fasta)
        
        print(data)
        return render_template(
            'show.html',
            title=app.config['TITLE'] + " - " + idCode,
            globals = glob_vars,
            data=data
        )
    
    
    
    return app
