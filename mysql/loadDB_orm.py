import re
import sys
import os
import argparse
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
# Import ORM models
from models.pdb_models import (
    Base, Author, Entry, CompType, ExpClasse, ExpType,
    Sequence as PDBSequence, Source, author_entry_table, entry_source_table
)

# Database credentials
if 'SQL_USERNAME' not in os.environ or 'SQL_PASSWORD' not in os.environ:
    sys.exit("Environment variables SQL_USERNAME and SQL_PASSWORD must be set")

# CLI args
parser = argparse.ArgumentParser(description='Load PDB data into DB')
parser.add_argument('-i', '--input_dir', default='.', help='Directory containing input files (default: current dir)')
parser.add_argument('--build_db', action='store_true', help='Create database tables from models and exit')
parser.add_argument('--database', action='store', help='Database name to connect to', default='pdb')
parser.add_argument('--host', action='store', help='Database host', default='localhost')
args = parser.parse_args()
INPUT_DIR = os.path.abspath(args.input_dir)

# If requested, create database and tables, then exit
if args.build_db:
    print(f"Creating database '{args.database}'...")
    # Connect to MySQL server without specifying a database
    admin_engine = create_engine(
        f"mysql+pymysql://{os.environ['SQL_USERNAME']}:{os.environ['SQL_PASSWORD']}@{args.host}?charset=utf8mb4",
        echo=False,
    )
    with admin_engine.connect() as conn:
        # Create database if it doesn't exist
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{args.database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
        conn.commit()
        print(f"Database '{args.database}' created successfully.")

    # Create engine and build schema
    engine = create_engine(
        f"mysql+pymysql://{os.environ['SQL_USERNAME']}:{os.environ['SQL_PASSWORD']}@{args.host}/{args.database}?charset=utf8mb4",
        echo=False,
    )
    print("Building database schema from models...")
    Base.metadata.create_all(engine)
    print("Database schema created.")
    sys.exit(0)

# Create engine and session for normal operation
engine = create_engine(
    f"mysql+pymysql://{user}:{passwd}@{args.host}/{args.database}?charset=utf8mb4",
    echo=False,
)
Session = sessionmaker(bind=engine)
session = Session()

# Turn off FKs (raw SQL for MySQL)
session.execute(text("SET FOREIGN_KEY_CHECKS=0"))

# Clean tables. Delete from association/child tables first
print("Cleaning tables...")
# association table
session.execute(author_entry_table.delete())
# entry_has_source
session.execute(entry_source_table.delete())
# sequence
session.execute(text("DELETE FROM sequences"))
# entry
session.execute(text("DELETE FROM entries"))
# sources
session.execute(text("DELETE FROM sources"))
# authors
session.execute(text("DELETE FROM authors"))
# expTypes, compTypes, expClasses
session.execute(text("DELETE FROM expTypes"))
session.execute(text("DELETE FROM compTypes"))
session.execute(text("DELETE FROM expClasses"))
session.commit()

# Reset AUTO_INCREMENT where applicable
for tbl in ('sources','authors','expTypes','compTypes','expClasses'):
    try:
        session.execute(text(f"ALTER TABLE {tbl} AUTO_INCREMENT=1"))
    except Exception:
        pass
session.commit()

# ------------------ Authors ------------------
print("Authors...")
AUTHORS = {}  # name -> Author instance
author_entries = []  # (author_name, idCode)
author_entry_seen = set()  # track (author_name, idCode) to avoid duplicates
try:
    with open(os.path.join(INPUT_DIR, "author.idx"), 'r') as AUTS:
        for line in AUTS:
            line = line.rstrip()
            if ' ; ' in line:
                idCode, author_name = line.split(" ; ", 1)
                if not idCode or not author_name:
                    continue
                if author_name not in AUTHORS:
                    a = Author(author=author_name)
                    session.add(a)
                    session.flush()  # obtain idAuthor
                    AUTHORS[author_name] = a
                key = (author_name, idCode)
                if key not in author_entry_seen:
                    author_entries.append((author_name, idCode))
                    author_entry_seen.add(key)
    print(f"Total unique authors: {len(AUTHORS)}")
    session.commit()
except IOError as e:
    print(f"Error reading author.idx: {str(e)}")
    session.rollback()
    sys.exit(1)
print("ok")

# ------------------ Sources ------------------
print("Sources...")
SOURCES = {}  # source string -> Source instance
source_entries = []  # (idCode, source_string)
try:
    with open(os.path.join(INPUT_DIR, "source.idx"), 'r') as SOUR:
        for line in SOUR:
            line = line.rstrip()
            if ' ' not in line:
                continue
            idCode, source_str = line.split(maxsplit=1)
            if not source_str or len(idCode) != 4:
                continue
            for s in source_str.split('; '):
                if s not in SOURCES:
                    so = Source(source=s)
                    session.add(so)
                    session.flush()
                    SOURCES[s] = so
                source_entries.append((idCode, s))
    print(f"Total unique sources: {len(SOURCES)}")
    session.commit()
except IOError as e:
    print(f"Error reading source.idx: {str(e)}")
    session.rollback()
    sys.exit(1)
print("ok")

# ------------------ Entries & ExpTypes ------------------
print("Entries...")
ExpTypes = {}  # name -> ExpType instance
expTypesbyCode = {}
try:
    with open(os.path.join(INPUT_DIR, "entries.idx"), 'r') as ENTR:
        for line in ENTR:
            line = line.rstrip()
            if "\t" not in line:
                continue
            idCode, header, ascDate, compound, source_field, authorList, resol, expTypeName = line.split("\t")
            if len(idCode) != 4:
                continue
            if ',' in str(resol):
                resol = resol.split(",")[0]
            if resol != 'NOT':
                try:
                    resol_val = float(resol)
                except ValueError:
                    print("Invalid resolution value: -", resol, "- for entry", idCode)
                    resol_val = 0
            else:
                resol_val = 0
            compound = compound[:255]

            # ensure expType exists
            if expTypeName not in ExpTypes:
                et = ExpType(ExpType=expTypeName)
                session.add(et)
                session.flush()
                ExpTypes[expTypeName] = et
            else:
                et = ExpTypes[expTypeName]

            entry = Entry(idCode=idCode, header=header, accessionDate=ascDate, compound=compound, resolution=resol_val)
            # link expType by id (set relationship)
            entry.expTypes = et
            session.add(entry)
            session.flush()
            expTypesbyCode[idCode] = expTypeName
    print(f"Total entries: {len(expTypesbyCode)}")
    session.commit()
except IOError as e:
    print(f"Error reading entries.idx: {str(e)}")
    session.rollback()
    sys.exit(1)
print("ok")

# ------------------ expClasse and compType mappings ------------------
print("Entry types...")
expClasses = {}
compTypes = {}
try:
    with open(os.path.join(INPUT_DIR, 'pdb_entry_type.txt'),'r') as EXPCL:
        for line in EXPCL:
            line = line.rstrip()
            if not line:
                continue
            idCode, compTypeName, expClassName = line.split()
            idCode = idCode.upper()
            # create expClasse if needed
            if expClassName not in expClasses:
                ec = ExpClasse(expClasse=expClassName)
                session.add(ec)
                session.flush()
                expClasses[expClassName] = ec
            else:
                ec = expClasses[expClassName]
            # create compType if needed
            if compTypeName not in compTypes:
                ct = CompType(type=compTypeName)
                session.add(ct)
                session.flush()
                compTypes[compTypeName] = ct
            else:
                ct = compTypes[compTypeName]

            # update ExpType.idExpClasse for the ExpType used by this entry
            expTypeName = expTypesbyCode.get(idCode)
            if expTypeName:
                et = ExpTypes.get(expTypeName)
                if et:
                    et.expClasses = ec
            # update entry.compTypes
            entry = session.get(Entry, idCode)
            if entry:
                entry.compTypes = ct
    session.commit()
except IOError as e:
    print(f"Error reading pdb_entry_type.txt: {str(e)}")
    session.rollback()
    sys.exit(1)

# ------------------ Sequences ------------------
print("Sequences...")
sequence_data = []
header_re = re.compile(r'^>([^_]*)_(.*)mol:(\S*) length:(\S*)')
try:
    with open(os.path.join(INPUT_DIR, "pdb_seqres.txt"), 'r') as SEQS:
        seq = ''
        idPdb = ''
        chain = ''
        header = ''
        for line in SEQS:
            line = line.rstrip()
            if line and line[0] == '>':
                if seq:
                    print("Adding sequence for", idPdb, "chain", chain)
                    s = PDBSequence(
                        idCode=idPdb.upper(),
                        chain=chain.replace(' ', ''),
                        sequence=seq.replace("\n", ""),
                        header=header
                    )
                    session.add(s)
                    seq = ''
                groups = header_re.match(line)
                if groups:
                    idPdb = groups.group(1)
                    chain = groups.group(2)
                header = line.replace('>', '')
            else:
                seq += line
        if seq:
            print("Adding last sequence for", idPdb, "chain", chain)
            s = PDBSequence(
                idCode=idPdb.upper(),
                chain=chain.replace(' ', ''),
                sequence=seq.replace("\n", ""),
                header=header
            )
            session.add(s)
    session.commit()
except IOError as e:
    print(f"Error reading pdb_seqres.txt: {str(e)}")
    session.rollback()
    sys.exit(1)
print("ok")

# ------------------ Link sources to entries ------------------
print("Linking sources to entries...")
try:
    for idCode, s in source_entries:
        source_obj = SOURCES.get(s)
        entry_obj = session.get(Entry, idCode)
        if source_obj and entry_obj:
            # use many-to-many relationship; avoid duplicates
            if source_obj not in entry_obj.sources:
                entry_obj.sources.append(source_obj)
    session.commit()
except Exception as e:
    print(f"Error linking sources: {e}")
    session.rollback()
    sys.exit(1)
print("ok")

# ------------------ Link authors to entries ------------------
print("Linking authors to entries...")
try:
    for author_name, idCode in author_entries:
        author_obj = AUTHORS.get(author_name)
        entry_obj = session.get(Entry, idCode)
        if author_obj and entry_obj:
            # use relationship append; SQLAlchemy will insert into association table
            author_obj.entries.append(entry_obj)
        #
    session.commit()
except Exception as e:
    print(f"Error linking authors: {e}")
    session.rollback()
    sys.exit(1)
print("ok")

# Re-enable foreign keys and close session
session.execute(text("SET FOREIGN_KEY_CHECKS=1"))
session.commit()
session.close()
print("Done")
