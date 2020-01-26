import os
import sys
import re
import uuid
import subprocess

from flask import Flask, render_template, session, request, url_for, redirect
from flask_mysqldb import MySQL

def prep_fasta(seq, header):
    return ">{}\n{}".format(header, re.sub('.{60}','\g<0>\n',seq))

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
        elif request.form['seqQuery'] or 'seqFile' in request.files:
            if request.files['seqFile'].filename:
                sequence = request.files['seqFile'].read().decode('ascii')
            else:
                sequence = request.form['seqQuery']
        # Blast
            session['query_seq'] = sequence
            return redirect(url_for('blast'))
        else:
        # Search
            return request.form

#
# Blast
#
    @app.route('/blast/')
    def blast():
        query = session['query_seq']
        if query[0] != '>': # Assumed not fasta
            query = ">User provided sequence\n{}".format(query)
        tmpFileName = os.path.join(app.instance_path, 'tmp/pdb') + str(uuid.uuid4())
        query_fasta_file = tmpFileName + '.query_fasta'
        blast_report_file = tmpFileName + '.blast_report'
        with open(query_fasta_file, 'w') as query_fasta:
            query_fasta.write(query)
        subprocess.run(
                app.config['BLAST_CMDLINE'] +\
                ' -query {} -out {}'.format(query_fasta_file,blast_report_file),
                shell=True
        )
        try:
            results = []
            with open(blast_report_file, 'r') as report:
                for line in report:
                    line = line.rstrip()
                    if len(line) > 1: 
                        id, header, ev = line.split("\t")
                        m = re.match('(....)_(.) mol:([^ ]*) length:([0-9]*) *(.*)', header)
                        results.append (
                            {
                                'idCode':m.group(1),
                                'sub':m.group(2),
                                'tip':m.group(3),
                                'desc':m.group(5),
                                'ev': ev
                            }
                        )
                    
        except IOError:
            return render_template(
                "error.html", 
                title=app.config['TITLE'] + " No Blast results found", 
                error_text='No results found. <p class="button" ><a href=\"\?new=1\">New Search</a></p>'
            )
        
        os.remove(query_fasta_file)
        os.remove(blast_report_file)
        
        return render_template(
                'blast_output.html',
                title=app.config['TITLE'] + " - Blast search",
                count=len(results),
                results=results
        )
        
#   
# Show Structure
#
    @app.route('/show/<idCode>')
    def show(idCode):
        glob_vars = globals()
        cur = mysql.connection.cursor()
        rs = cur.execute("SELECT e.* from entry e where e.idCode='{}'".format(idCode))
        if not rs:
            return render_template(
                "error.html", 
                title=app.config['TITLE'], 
                error_text='Structure not found ({})'.format(idCode)
            )
        columns = [col[0] for col in cur.description]
        data = dict(zip(columns, cur.fetchone()))
        rs = cur.execute("SELECT a.author from author a, author_has_entry ae where ae.idCode='{}' and a.idAuthor = ae.idAuthor order by a.author".format(idCode))
        data['author_list'] = ', '.join([aut[0] for aut in cur.fetchall()])
        rs = cur.execute("SELECT s.source from source s, entry_has_source es where es.idCode='{}' and s.idSource = es.idSource order by s.source".format(idCode))
        data['source_list'] = ', '.join([sc[0] for sc in cur.fetchall()])
        rs = cur.execute("SELECT * from sequence s where s.idCode='{}' order by s.chain".format(idCode))
        data['sequences'] = []
        for sq in cur.fetchall():
            data['sequences'].append(prep_fasta(sq[2], sq[3]))

        return render_template(
            'show.html',
            title=app.config['TITLE'] + " - " + idCode,
            globals = glob_vars,
            data=data
        )
    
    
    
    return app

  