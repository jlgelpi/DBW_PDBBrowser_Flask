import os
import sys
import re
import uuid
import subprocess

from flask import Flask, render_template, session, request, url_for, redirect
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

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
    for key, value in glob_vars['compTypesArray'].items():
        if 'idCompType['+ str(key) +']' in form_data:
            ORConds.append(" e.idCompType = " + str(key));
    if ORConds:
        ANDconds.append('(' + ' OR '.join(ORConds) + ')')
    # Classe of experiment
    ORConds = []
    for key, value in glob_vars['expClassesArray'].items():
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
            "expTypes et, author_has_entry ae, authors a, sources s, entry_has_source es, entries e, sequences sq WHERE " +\
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
    db = SQLAlchemy(app)

#
# Global data
#
    def get_globals():
        globals = {}
        globals['compTypesArray'] = {}
        result = db.session.execute(text("SELECT * FROM compTypes"))
        for row in result:
            globals['compTypesArray'][row[0]] = row[1]
        globals['expClassesArray'] = {}
        result = db.session.execute(text("SELECT * FROM expClasses"))
        for row in result:
            globals['expClassesArray'][row[0]] = row[1]
        globals['expTypesArray'] = {}
        result = db.session.execute(text("SELECT idExptype, ExpType FROM expTypes"))
        for row in result:
            globals['expTypesArray'][row[0]] = row[1]
        return globals

#
# Index
#

    @app.route('/')
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
            globals=glob_vars,
            ext_url=app.config["BASE_URL"]
        )
#
# Search page
#
    @app.route('/search/', methods=['GET', 'POST'])
    def search():
        glob_vars = get_globals()
        session['query_data'] = request.form
        if request.form['idCode']:
            #PDB ID
            return redirect(app.config["BASE_URL"] + url_for('show', idCode=request.form['idCode']))
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
            return redirect(app.config['BASE_URL'] + url_for('blast'))
        else:
            # Search
            sql = prep_sql(request.form, glob_vars, app.config['TEXT_FIELDS'])
            #print(sql)
            results = []
            result = db.session.execute(text(sql))
            rows = result.fetchall()
            if not rows:
                return render_template(
                    "error.html",
                    title=app.config['TITLE'] + " No results found",
                    error_text='No results found',
                )
            else:
                for data in rows:
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
                    title=app.config['TITLE'] + " - Database search",
                    count=len(results),
                    results=results,
                    ext_url = app.config['BASE_URL'],
                )

#
# Blast
#
    @app.route('/blast/')
    def blast():
        results, error = run_blast(app, session['query_seq'])
        if error:
            return render_template(
                "error.html",
                title=app.config['TITLE'] + " No Blast results found",
                error_text='No results found',
            )
        else:
            return render_template(
                'blast_output.html',
                title=app.config['TITLE'] + " - Blast search",
                count=len(results),
                results=results,
                ext_url = app.config['BASE_URL'],
            )

#
# Show Structure
#
    @app.route('/show/<idCode>')
    def show(idCode):
        glob_vars = get_globals()
        result = db.session.execute(text("SELECT e.* FROM entries e WHERE e.idCode = :id"), {"id": idCode})
        row = result.fetchone()
        if not row:
            return render_template(
                "error.html",
                title=app.config['TITLE'],
                error_text='Structure not found ({})'.format(idCode)
            )
        columns = list(result.keys())
        data = dict(zip(columns, row))
        result = db.session.execute(
            text("SELECT a.author FROM authors a, author_has_entry ae WHERE ae.idCode = :id AND a.idAuthor = ae.idAuthor ORDER BY a.author"),
            {"id": idCode}
        )
        data['author_list'] = ', '.join([aut[0] for aut in result.fetchall()])
        result = db.session.execute(
            text("SELECT s.source FROM sources s, entry_has_source es WHERE es.idCode = :id AND s.idSource = es.idSource ORDER BY s.source"),
            {"id": idCode}
        )
        data['source_list'] = ', '.join([sc[0] for sc in result.fetchall()])
        result = db.session.execute(
            text("SELECT * FROM sequences s WHERE s.idCode = :id ORDER BY s.chain"),
            {"id": idCode}
        )
        data['sequences'] = []
        for sq in result.fetchall():
            data['sequences'].append(prep_fasta(sq[2], sq[3]))

        return render_template(
            'show.html',
            title=app.config['TITLE'] + " - " + idCode,
            globals = glob_vars,
            data=data,
            ext_url = app.config['BASE_URL'],
        )

    return app
