import os
import sys
import re
import uuid
import subprocess

from flask import Flask, render_template, session, request, url_for, redirect
from flask_mysqldb import MySQL

def prep_fasta(seq, header):
    return ">{}\n{}".format(header, re.sub('.{60}','\g<0>\n',seq))

def run_blast(app, query):
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
        return [], True

    os.remove(query_fasta_file)
    os.remove(blast_report_file)
    
    return results, False

def prep_sql(form_data, glob_vars, text_fields):
    ''' Prepare SQL from search form '''    
    ANDconds = ["True"] # required to fulfill SQL syntax if form is empty
    #Resolution, we consider only cases where user has input something
    if form_data['minRes'] != '0.0' or form_data['maxRes'] != 'Inf':
        if form_data['minRes'] != '0.0':
            ANDconds.append("e.resolution >= " + form_data['minRes'])
        if form_data['maxRes'] != 'Inf':
            ANDconds.append("e.resolution <= " + form_data['maxRes'])
    # Compound type ORconds holds options selected
    ORConds = []
    for key, value in glob_vars['compTypeArray'].items():
        if 'idCompType['+ str(key) +']' in form_data:
            ORConds.append(" e.idCompType = " + str(key));
    if ORConds:
        ANDconds.append('(' + ' OR '.join(ORConds) + ')')
    # Classe of experiment
    ORConds = []
    for key, value in glob_vars['expClasseArray'].items():
        if 'idExpClasse[' + str(key) + ']' in form_data:
            ORConds.append(' et.idExpClasse = ' + str(key))
    if ORConds:
        ANDconds.append('(' + ' OR '.join(ORConds) + ')')
    #text query, adapted to use fulltext indexes, app.config['TEXT_FIELDS'] is defined in config
    #lists all text fields to be searched in.
    if form_data['query']:
        ORConds = []
        for field in text_fields:
            ORConds.append("MATCH (" + field + ") AGAINST ('" + form_data['query'] + "' IN BOOLEAN MODE)")
            #ORConds.append("MATCH (" + field + ") AGAINST ('" + form_data['query'] + ")")
        ANDconds.append("(" + " OR ".join(ORConds) +  ")")
    
    #  main SQL string, make sure that all tables are joint, and relationships included

    sql = "SELECT distinct e.idCode,e.header,e.compound,e.resolution,s.source,et.expType FROM " +\
            "expType et, author_has_entry ae, author a, source s, entry_has_source es, entry e, sequence sq WHERE " +\
            "e.idExpType=et.idExpType AND " +\
            "ae.idCode=e.idCode and ae.idAuthor=a.idAuthor AND " +\
            "es.idCode=e.idCode and es.idsource=s.idSource AND " +\
            "e.idCode = sq.idCode AND " + " AND ".join(ANDconds)
    if 'nolimit' not in form_data:
        sql += " LIMIT 5000" # Just to avoid too long listings when testing
    
    return sql

#===============================================================================

def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path, exist_ok=True)
        os.makedirs(os.path.join(app.instance_path, 'tmp'), exist_ok=True)
    except OSError as e:
        sys.exit(e)
    app.config.from_pyfile('config.py', silent=False)
    mysql = MySQL(app)
   
#
# Global data
#
    def get_globals():
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

    @app.route(app.config['BASE_URL'])
    def index():
        glob_vars = get_globals()
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
            globals=glob_vars
        )
#
# Search page
#
    @app.route(app.config['BASE_URL'] + 'search/', methods=['GET', 'POST'])
    def search():
        glob_vars = get_globals()
        session['query_data'] = request.form
        if request.form['idCode']:
            #PDB ID 
            return redirect(url_for('show', idCode=request.form['idCode']))
        elif request.form['seqQuery'] or request.files['seqFile'].filename:
            if request.files['seqFile'].filename:
                sequence = request.files['seqFile'].read().decode('ascii')
            else:
                sequence = request.form['seqQuery']
            # Blast
            if not sequence: 
                return render_template(
                    "error.html", 
                    title=app.config['TITLE'] + " No input sequence found", 
                    error_text='No input sequence found'
                )
            session['query_seq'] = sequence        
            return redirect(url_for('blast'))
        else:
            # Search
            sql = prep_sql(request.form, glob_vars, app.config['TEXT_FIELDS'])
            #print(sql)
            results = []
            cur = mysql.connection.cursor()
            rs = cur.execute(sql)
            if not rs:
                return render_template(
                    "error.html", 
                    title=app.config['TITLE'] + " No results found", 
                    error_text='No results found'
                )
            else:
                for data in cur.fetchall():
                    results.append(
                        {
                            'idCode' : data[0],
                            'header' : data[1].lower().capitalize(),
                            'compound': data[2].lower().capitalize(),
                            'resolution': data[3],
                            'source': data[4].lower().capitalize(),
                            'expType' : data[5]
                        }
                    )
                    
                return render_template(
                    'search_output.html',
                    title=app.config['TITLE'] + " - Blast search",
                    count=len(results),
                    results=results
                )
        
#
# Blast
#
    @app.route(app.config['BASE_URL'] + 'blast/')
    def blast():
        results, error = run_blast(app, session['query_seq'])
        if error:
            return render_template(
                "error.html", 
                title=app.config['TITLE'] + " No Blast results found", 
                error_text='No results found'
            )
        else:
            return render_template(
                'blast_output.html',
                title=app.config['TITLE'] + " - Blast search",
                count=len(results),
                results=results
            )
        
#   
# Show Structure
#
    @app.route(app.config['BASE_URL'] + 'show/<idCode>')
    def show(idCode):
        glob_vars = get_globals()
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

    @app.route('/blast')
    def blast():
        return "Not yet"
    
    return app

  
