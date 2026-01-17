''' ETL for PDBData into MySQL database - pymysql driver, plain SQL'''

import re
import os
import sys
import argparse
import pymysql

# Parse command line arguments
parser = argparse.ArgumentParser(description='Load PDB data into MySQL database')
parser.add_argument('--data_dir', type=str, default='.', help='Directory containing data files (default: current directory)')
parser.add_argument('--host', type=str, default='localhost', help='MySQL host (default: localhost)')
parser.add_argument('--database', type=str, default='pdb', help='MySQL database name (default: pdb)')   
args = parser.parse_args()

# Establish MySQL connection
connection = pymysql.connect(
    host=args.host,
    user=os.environ["SQL_USERNAME"],
    password=os.environ["SQL_PASSWORD"],
    database=args.database,
    charset='utf8mb4',
    autocommit=True
)

## Turn off FKs
connection.cursor().execute("SET FOREIGN_KEY_CHECKS=0")

## Clean Tables !!
for tab in (
    'entry', 'source', 'sequence', 'author', 'author_has_entry', 
    'expType', 'comptype', 'entry_has_source', 'expClasse'):
    try:
        print("Cleaning {}".format(tab))
        connection.cursor().execute("DELETE FROM "+ tab)
    except OSError as e:
        sys.exit(e.msg)
    
        
for tab in  ('source','author','expType','comptype','expClasse'):
    connection.cursor().execute("ALTER TABLE " + tab + " AUTO_INCREMENT=1")
print("Authors...")
AUTHORS = {}
author_has_entry = {}
sthAuthor = "INSERT INTO author (author) VALUES (%s)"
sthEntryAuthor = "INSERT INTO author_has_entry VALUES (%s,%s)"
with open(os.path.join(args.data_dir, 'author.idx'), 'r') as AUTS:
    for line in AUTS:
        line = line.rstrip()
        if ' ; ' in line:
            idCode, author = line.split(" ; ")
            if not idCode or not author:
                continue
            if author and author not in AUTHORS: 
                with connection.cursor() as c:
                    c.execute(sthAuthor, author)
                    author_id = c.lastrowid                    
                    AUTHORS[author]=author_id
                    aek = "{}{}".format(author_id, idCode)
                    if aek not in author_has_entry: 
                        c.execute(sthEntryAuthor, (author_id, idCode))
                        author_has_entry[aek] = True
print("ok")
##
##
print ("Sources...")
SOURCES = {}
sthSource = "INSERT INTO source (source) VALUES (%s)"
sthEntrySource = "INSERT INTO entry_has_source (idCode,idSource) VALUES (%s, %s)"
with open(os.path.join(args.data_dir, 'source.idx'), 'r') as SOUR:
    for line in SOUR:
        line = line.rstrip()
        if ' ' not in line:
            continue
        idCode, source  = line.split(maxsplit=1)
        if not source or len(idCode) != 4:
            continue
        for s in source.split('; '):
            with connection.cursor() as c:
                if s not in SOURCES:
                    c.execute(sthSource, s)
                    SOURCES[s] = c.lastrowid
                c.execute(sthEntrySource, (idCode, SOURCES[s]))
print("ok")
##
##
print("Entries...")

sthEntry = "INSERT INTO entry (idCode, header, ascessionDate, compound, resolution) VALUES (%s, %s, %s, %s, %s)"
ExpTypes = {}
sthExpType = "INSERT INTO expType (ExpType) VALUES (%s)"
sthEntryExpType = "UPDATE entry SET idExpType=%s WHERE idCode=%s"
expTypesbyCode = {}

with open(os.path.join(args.data_dir, 'entries.idx'), 'r') as ENTR:
    for line in ENTR:
        line = line.rstrip()
        if "\t" not in line:
            continue
        idCode, header, ascDate, compound, source, authorList, resol, expType = line.split("\t")
        if len(idCode) != 4:
            continue
        if 'NOT' in resol:
            resol = 0
        if ',' in str(resol):
            r = resol.split(",")
            resol = r[0]
        compound = compound[:255]
        with connection.cursor() as c:
            c.execute(sthEntry, (idCode, header, ascDate, compound, resol))
            if expType not in ExpTypes:
                c.execute(sthExpType, expType)
                ExpTypes[expType] = c.lastrowid
            c.execute(sthEntryExpType, (ExpTypes[expType],idCode))
            expTypesbyCode[idCode] = expType
print("ok")
##
##
expClasses = {}
compTypes = {}
sthExpClasse = 'INSERT INTO expClasse (expClasse) VALUES (%s)'
sthcompType = 'INSERT INTO comptype (type) VALUES (%s)'
entryUpdate = 'UPDATE entry SET idCompType=%s WHERE idCode=%s'
expTypeUpdate = 'UPDATE expType SET idExpClasse=%s where ExpType=%s'
with open(os.path.join(args.data_dir, 'pdb_entry_type.txt'), 'r') as EXPCL:
    for line in EXPCL:
        line = line.rstrip()
        idCode, compType, expClass = line.split()
        idCode = idCode.upper()
        with connection.cursor() as c:
            if expClass not in expClasses:
                c.execute(sthExpClasse, expClass)
                expClasses[expClass] = c.lastrowid
            if compType not in compTypes:
                c.execute(sthcompType, compType)
                compTypes[compType] = c.lastrowid
            c.execute(expTypeUpdate, (expClasses[expClass], expTypesbyCode[idCode]))
            c.execute(entryUpdate, (compTypes[compType],idCode))
##Sequence
print("Sequences...")
#codes = []
#CODES = {}
sthInsert= "INSERT INTO sequence (idCode,chain,sequence,header) VALUES (%s,%s,%s,%s)"
seq = ''
idPdb = ''
chain = ''
header = ''
header_re = re.compile(r'^>([^_]*)_(.*)mol:(\S*) length:(\S*)')
with open(os.path.join(args.data_dir, 'pdb_seqres.txt'), 'r') as SEQS: 
    for line in SEQS:
        line =line.rstrip()
        if '>' == line[0]:
            if seq:
                seq = seq.replace("\n","")
                idPdb = idPdb.upper()
                chain = chain.replace(' ','')
                connection.cursor().execute(sthInsert,(idPdb,chain,seq, header))
                seq = ''
            groups = header_re.match(line)
            idPdb = groups.group(1)
            chain = groups.group(2)
            header = line.replace('>','')
        else:
            seq += line
print("ok")
connection.cursor().execute("SET FOREIGN_KEY_CHECKS=1")
