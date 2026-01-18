"""Load PDB data into MongoDB using mongoengine ODM models."""

import re
import sys
import os
import argparse
from mongoengine import connect, disconnect
from datetime import datetime


# CLI args
parser = argparse.ArgumentParser(description='Load PDB data into MongoDB')
parser.add_argument('-i', '--input_dir', default='.', help='Directory containing input files (default: current dir)')
parser.add_argument('--drop_db', action='store_true', help='Drop all collections before loading')
parser.add_argument('--host', default='localhost', help='MongoDB host (default: localhost)')
parser.add_argument('--port', type=int, default=27017, help='MongoDB port (default: 27017)')
parser.add_argument('--database', default='pdb', help='Database name (default: pdb)')
args = parser.parse_args()
INPUT_DIR = os.path.abspath(args.input_dir)

# Import MongoDB models
from models.pdb_models import (
    Author, Entry, CompoundType, ExperimentalClass, ExperimentalType,
    Source, Sequence
)

# Connect to MongoDB
try:
    if os.environ.get("MDB_USERNAME") and os.environ.get("MDB_PASSWORD"):
        connect(
            args.database,
            host=args.host,
            port=args.port,
            username=os.environ["MDB_USERNAME"],
            password=os.environ["MDB_PASSWORD"]
        )
    else:
        connect(args.database, host=args.host, port=args.port)
    print(f"Connected to MongoDB at {args.host}:{args.port}/{args.database}")
except Exception as e:
    print(f"Error connecting to MongoDB: {str(e)}")
    sys.exit(1)

# If requested, drop all collections
if args.drop_db:
    print("Dropping all collections...")
    try:
        Author.drop_collection()
        Entry.drop_collection()
        CompoundType.drop_collection()
        ExperimentalClass.drop_collection()
        ExperimentalType.drop_collection()
        Source.drop_collection()
        print("All collections dropped.")
    except Exception as e:
        print(f"Warning: Error dropping collections: {e}")

# Create indexes
print("Creating indexes...")
try:
    Author.ensure_indexes()
    Entry.ensure_indexes()
    CompoundType.ensure_indexes()
    ExperimentalClass.ensure_indexes()
    ExperimentalType.ensure_indexes()
    Source.ensure_indexes()
    print("Indexes created.")
except Exception as e:
    print(f"Warning: Error creating indexes: {e}")

# ------------------ Authors ------------------
print("Loading Authors...")
AUTHORS = {}  # name -> Author instance
author_entries = []  # (author_name, idCode)
author_entry_seen = set()  # track (author_name, idCode) to avoid duplicates
try:
    author_id = 1
    with open(os.path.join(INPUT_DIR, "author.idx"), 'r') as AUTS:
        for line in AUTS:
            line = line.rstrip()
            if ' ; ' not in line:
                continue
            idCode, author_name = line.split(" ; ", 1)
            if not idCode or not author_name:
                continue
            if author_name not in AUTHORS:
                try:
                    a = Author(id_author=author_id, author=author_name)
                    a.save()
                    AUTHORS[author_name] = a
                    author_id += 1
                except Exception as e:
                    print(f"Error saving author '{author_name}': {e}")
                    continue
            key = (author_name, idCode)
            if key not in author_entry_seen:
                author_entries.append((author_name, idCode))
                author_entry_seen.add(key)
except IOError as e:
    print(f"Error reading author.idx: {str(e)}")
    sys.exit(1)
print(f"Loaded {len(AUTHORS)} authors. {len(author_entries)} author-entry associations.")

# ------------------ Sources ------------------
print("Loading Sources...")
SOURCES = {}  # source string -> Source instance
source_entries = []  # (idCode, source_string)
source_entries_seen = set()
try:
    source_id = 1
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
                    try:
                        so = Source(id_source=source_id, source=s)
                        so.save()
                        SOURCES[s] = so
                        source_id += 1
                    except Exception as e:
                        print(f"Error saving source '{s}': {e}")
                        continue
                key = (idCode, s)
                if key not in source_entries_seen:
                    source_entries.append((idCode, s))
                    source_entries_seen.add(key)
except IOError as e:
    print(f"Error reading source.idx: {str(e)}")
    sys.exit(1)
print(f"Loaded {len(SOURCES)} sources. {len(source_entries)} source-entry associations.")

# ------------------ ExperimentalClass and CompoundType ------------------
print("Loading Experimental Classes and Compound Types...")
expClasses = {}  # name -> ExperimentalClass instance
compTypes = {}  # name -> CompoundType instance
expMetabyCode = {}  # idCode -> (expClassName, compTypeName)
try:
    exp_classe_id = 1
    comp_type_id = 1
    with open(os.path.join(INPUT_DIR, 'pdb_entry_type.txt'), 'r') as EXPCL:
        for line in EXPCL:
            line = line.rstrip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            idCode, compTypeName, expClassName = parts[0], parts[1], parts[2]
            idCode = idCode.upper()

            # Create ExperimentalClass if needed
            if expClassName not in expClasses:
                try:
                    ec = ExperimentalClass(id_exp_classe=exp_classe_id, exp_classe=expClassName)
                    ec.save()
                    expClasses[expClassName] = ec
                    exp_classe_id += 1
                except Exception as e:
                    print(f"Error saving exp class '{expClassName}': {e}")
                    continue

            # Create CompoundType if needed
            if compTypeName not in compTypes:
                try:
                    ct = CompoundType(id_comp_type=comp_type_id, comp_type=compTypeName)
                    ct.save()
                    compTypes[compTypeName] = ct
                    comp_type_id += 1
                except Exception as e:
                    print(f"Error saving compound type '{compTypeName}': {e}")
                    continue

            expMetabyCode[idCode] = (expClassName, compTypeName)
except IOError as e:
    print(f"Error reading pdb_entry_type.txt: {str(e)}")
    sys.exit(1)
print(f"Loaded {len(expClasses)} experimental classes and {len(compTypes)} compound types.")


# ------------------ Entries ------------------
print("Loading Entries...")
entries_created = 0
expTypesByCode = {}  # idCode -> (expType, expClassName)
try:
    with open(os.path.join(INPUT_DIR, "entries.idx"), 'r') as ENTR:
        for line in ENTR:
            line = line.rstrip()
            if "\t" not in line:
                continue
            fields = line.split("\t")
            if len(fields) < 8:
                continue

            idCode, header, ascDate, compound, source_field, authorList, resol, expTypeName = fields[:8]

            if len(idCode) != 4:
                continue

            # Parse resolution
            if ',' in str(resol):
                resol = resol.split(",")[0]
            resol_val = None
            if resol != 'NOT':
                try:
                    resol_val = float(resol)
                except ValueError:
                    print(f"Invalid resolution value: '{resol}' for entry {idCode}")

            compound = compound[:255] if compound else ""
            idCode = idCode.upper()

            # Get references
            exp_type_ref = None
            comp_type_ref = None
            if idCode in expMetabyCode:
                expClassName, compTypeName = expMetabyCode[idCode]
            
            exp_classe_ref = ExpClasses.get(expClassName)
            comp_type_ref = compTypes.get(compTypeName)
            exp_type_ref = ExperimentalType(expTypeName) if expTypeName else None
            exp_type_ref.add_exp_class(exp_classe_ref) if exp_classe_ref else None
            exp_type_ref.save() if exp_type_ref else None
            
            
            try:
                entry = Entry(
                    id_code=idCode,
                    header=header,
                    accession_date=ascDate,
                    compound=compound,
                    resolution=resol_val,
                    id_exp_classe=exp_classe_ref,
                    id_comp_type=comp_type_ref,
                    id_exp_type=exp_type_ref
                )
                entry.save()
                entries_created += 1
            except Exception as e:
                print(f"Error saving entry {idCode}: {e}")
                continue

except IOError as e:
    print(f"Error reading entries.idx: {str(e)}")
    sys.exit(1)
print(f"Loaded {entries_created} entries.")

# ------------------ Sequences ------------------
print("Loading Sequences...")
header_re = re.compile(r'^>([^_]*)_(.*)mol:(\S*) length:(\S*)')
sequences_added = 0
try:
    with open(os.path.join(INPUT_DIR, "pdb_seqres.txt"), 'r') as SEQS:
        seq = ''
        idPdb = ''
        chain = ''
        header = ''
        for line in SEQS:
            line = line.rstrip()
            if line and line[0] == '>':
                if seq and idPdb:
                    try:
                        entry = Entry.objects(id_code=idPdb.upper()).first()
                        if entry:
                            entry.add_sequence(
                                chain=chain.replace(' ', ''),
                                sequence=seq.replace("\n", ""),
                                header=header
                            )
                            entry.save()
                            sequences_added += 1
                    except Exception as e:
                        print(f"Error adding sequence for {idPdb} chain {chain}: {e}")
                    seq = ''

                groups = header_re.match(line)
                if groups:
                    idPdb = groups.group(1)
                    chain = groups.group(2)
                header = line.replace('>', '')
            else:
                seq += line

        # Handle last sequence
        if seq and idPdb:
            try:
                entry = Entry.objects(id_code=idPdb.upper()).first()
                if entry:
                    entry.add_sequence(
                        chain=chain.replace(' ', ''),
                        sequence=seq.replace("\n", ""),
                        header=header
                    )
                    entry.save()
                    sequences_added += 1
            except Exception as e:
                print(f"Error adding sequence for {idPdb} chain {chain}: {e}")
except IOError as e:
    print(f"Error reading pdb_seqres.txt: {str(e)}")
    sys.exit(1)
print(f"Loaded {sequences_added} sequences.")

# ------------------ Link sources to entries ------------------
print("Linking sources to entries...")
sources_linked = 0
try:
    for idCode, source_name in source_entries:
        source_obj = SOURCES.get(source_name)
        if source_obj:
            try:
                entry = Entry.objects(id_code=idCode.upper()).first()
                if entry:
                    entry.sources.append(source_obj)
                    entry.save()
                    sources_linked += 1
            except Exception as e:
                print(f"Error linking source '{source_name}' to entry {idCode}: {e}")
                continue
except Exception as e:
    print(f"Error linking sources: {e}")
    sys.exit(1)
print(f"Linked {sources_linked} source-entry associations.")

# ------------------ Link authors to entries ------------------
print("Linking authors to entries...")
authors_linked = 0
try:
    for author_name, idCode in author_entries:
        author_obj = AUTHORS.get(author_name)
        if author_obj:
            try:
                entry = Entry.objects(id_code=idCode.upper()).first()
                if entry:
                    author_obj.entries.append(entry)
                    author_obj.save()
                    authors_linked += 1
            except Exception as e:
                print(f"Error linking author '{author_name}' to entry {idCode}: {e}")
                continue
except Exception as e:
    print(f"Error linking authors: {e}")
    sys.exit(1)
print(f"Linked {authors_linked} author-entry associations.")

# Close MongoDB connection
disconnect()
print("Done")
