BASE_URL = '' # No trailing /
SECRET_KEY = 'dev'
MYSQL_HOST = 'localhost'
MYSQL_USER = 'USER'
MYSQL_PASSWORD = 'PASS'
MYSQL_DB = 'pdb'
BLAST_HOME = 'Blast application home dir'
BLAST_DBDIR = BLAST_HOME + '/DBS'
BLAST_DBS = {'SwissProt': 'sprot', 'PDB': 'pdb'}
BLAST_EXE = BLAST_HOME + '/bin/blastp'
BLAST_CMDLINE = BLAST_EXE + ' -db ' + BLAST_DBDIR + '/' + BLAST_DBS['PDB'] + ' -evalue 0.001 -max_target_seqs 100 -outfmt "6 sseqid stitle evalue" '
TEXT_FIELDS = ['e.header', 'e.compound', 'a.author', 's.source', 'sq.header']
TITLE='PDB Browser (Flask edition)'
PDB_PREFIX='https://www.pdb.org/pdb/explore.do?structureId='
API_PREFIX='https://mmb.irbbarcelona.org/api/pdb/'
