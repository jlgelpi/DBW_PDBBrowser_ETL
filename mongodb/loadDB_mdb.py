import re
import sys
import os
import argparse
from mongoengine import connect, disconnect
from datetime import datetime

# Database configuration for MongoDB
mongodb_host = "localhost"
mongodb_port = 27017
database_name = "pdb"

# CLI args
parser = argparse.ArgumentParser(description='Load PDB data into MongoDB')
parser.add_argument('-i', '--input-dir', default='.', help='Directory containing input files (default: current dir)')
parser.add_argument('--drop-db', action='store_true', help='Drop all collections before loading')
args = parser.parse_args()
INPUT_DIR = os.path.abspath(args.input_dir)

# Import MongoDB models
from models.pdb_models import (
    Author, Entry, CompoundType, ExperimentalClass, ExperimentalType,
    Sequence, Source
)

# Connect to MongoDB
try:
    connect(database_name, host=mongodb_host, port=mongodb_port)
    print(f"Connected to MongoDB at {mongodb_host}:{mongodb_port}/{database_name}")
except Exception as e:
    print(f"Error connecting to MongoDB: {str(e)}")
    sys.exit(1)

# If requested, drop all collections
if args.drop_db:
    print("Dropping all collections...")
    Author.drop_collection()
    Entry.drop_collection()
    CompoundType.drop_collection()
    ExperimentalClass.drop_collection()
    ExperimentalType.drop_collection()
    Source.drop_collection()
    print("All collections dropped.")

# Create indexes
print("Creating indexes...")
Author.ensure_indexes()
Entry.ensure_indexes()
CompoundType.ensure_indexes()
ExperimentalClass.ensure_indexes()
ExperimentalType.ensure_indexes()
Source.ensure_indexes()
print("Indexes created.")

# ------------------ Authors ------------------
print("Loading Authors...")
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
                    try:
                        a = Author(id_author=len(AUTHORS) + 1, author=author_name)
                        a.save()
                        AUTHORS[author_name] = a
                    except Exception as e:
                        print(f"Error saving author {author_name}: {e}")
                        continue
                key = (author_name, idCode)
                if key not in author_entry_seen:
                    author_entries.append((author_name, idCode))
                    author_entry_seen.add(key)
except IOError as e:
    print(f"Error reading author.idx: {str(e)}")
    sys.exit(1)
print("ok")

# ------------------ Sources ------------------
print("Loading Sources...")
SOURCES = {}  # source string -> Source instance
source_entries = []  # (idCode, source_string)
try:
    with open(os.path.join(INPUT_DIR, "source.idx"), 'r') as SOUR:
        source_id = 1
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
                        print(f"Error saving source {s}: {e}")
                        continue
                source_entries.append((idCode, s))
except IOError as e:
    print(f"Error reading source.idx: {str(e)}")
    sys.exit(1)
print("ok")

# ------------------ ExperimentalClass and ExperimentalType ------------------
print("Loading Experimental Types...")
ExpTypes = {}  # name -> ExperimentalType instance
expTypesbyCode = {}
expClasses = {}
try:
    with open(os.path.join(INPUT_DIR, 'pdb_entry_type.txt'), 'r') as EXPCL:
        exp_type_id = 1
        exp_classe_id = 1
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
                    print(f"Error saving exp class {expClassName}: {e}")
                    continue

            # Create ExperimentalType if needed (will link to class)
            if expClassName not in ExpTypes and expClassName in expClasses:
                try:
                    et = ExperimentalType(
                        id_exp_type=exp_type_id,
                        exp_type=expClassName,
                        id_exp_classe=expClasses[expClassName]
                    )
                    et.save()
                    ExpTypes[expClassName] = et
                    exp_type_id += 1
                except Exception as e:
                    print(f"Error saving exp type {expClassName}: {e}")
                    continue

            if expClassName in expTypesbyCode:
                expTypesbyCode[idCode] = expClassName
except IOError as e:
    print(f"Error reading pdb_entry_type.txt: {str(e)}")
    sys.exit(1)
print("ok")

# ------------------ CompoundTypes ------------------
print("Loading Compound Types...")
compTypes = {}
try:
    with open(os.path.join(INPUT_DIR, 'pdb_entry_type.txt'), 'r') as COMPT:
        comp_type_id = 1
        for line in COMPT:
            line = line.rstrip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            compTypeName = parts[1]

            if compTypeName not in compTypes:
                try:
                    ct = CompoundType(id_comp_type=comp_type_id, type=compTypeName)
                    ct.save()
                    compTypes[compTypeName] = ct
                    comp_type_id += 1
                except Exception as e:
                    print(f"Error saving compound type {compTypeName}: {e}")
                    continue
except IOError as e:
    print(f"Error reading pdb_entry_type.txt: {str(e)}")
    sys.exit(1)
print("ok")

# ------------------ Entries ------------------
print("Loading Entries...")
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
            if resol != 'NOT':
                try:
                    resol_val = float(resol)
                except ValueError:
                    print(f"Invalid resolution value: '{resol}' for entry {idCode}")
                    resol_val = None
            else:
                resol_val = None

            compound = compound[:255] if compound else ""

            # Get references
            exp_type_ref = ExpTypes.get(expTypeName)
            comp_type_ref = compTypes.get(expTypeName)

            try:
                entry = Entry(
                    id_code=idCode.upper(),
                    header=header,
                    accession_date=ascDate,
                    compound=compound,
                    resolution=resol_val,
                    id_exp_type=exp_type_ref,
                    id_comp_type=comp_type_ref
                )
                entry.save()
                expTypesbyCode[idCode.upper()] = expTypeName
            except Exception as e:
                print(f"Error saving entry {idCode}: {e}")
                continue

    # Now update entries with compound types from pdb_entry_type.txt
    with open(os.path.join(INPUT_DIR, 'pdb_entry_type.txt'), 'r') as EXPCL:
        for line in EXPCL:
            line = line.rstrip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            idCode = parts[0].upper()
            compTypeName = parts[1]

            try:
                entry = Entry.objects(id_code=idCode).first()
                if entry and compTypeName in compTypes:
                    entry.id_comp_type = compTypes[compTypeName]
                    entry.save()
            except Exception as e:
                print(f"Error updating entry {idCode} with compound type: {e}")
                continue

except IOError as e:
    print(f"Error reading entries.idx: {str(e)}")
    sys.exit(1)
print("ok")

# ------------------ Sequences ------------------
print("Loading Sequences...")
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
            except Exception as e:
                print(f"Error adding sequence for {idPdb} chain {chain}: {e}")
except IOError as e:
    print(f"Error reading pdb_seqres.txt: {str(e)}")
    sys.exit(1)
print("ok")

# ------------------ Link sources to entries ------------------
print("Linking sources to entries...")
try:
    for idCode, source_name in source_entries:
        source_obj = SOURCES.get(source_name)
        if source_obj:
            try:
                entry = Entry.objects(id_code=idCode.upper()).first()
                if entry:
                    entry.add_source(source_obj)
                    entry.save()

                    # Also create AuthorHasEntry record
                    try:
                        record = EntryHasSource(
                            id_code=entry,
                            id_source=source_obj
                        )
                        record.save()
                    except Exception:
                        pass  # Avoid duplicate key errors
            except Exception as e:
                print(f"Error linking source {source_name} to entry {idCode}: {e}")
                continue
except Exception as e:
    print(f"Error linking sources: {e}")
    sys.exit(1)
print("ok")

# ------------------ Link authors to entries ------------------
print("Linking authors to entries...")
try:
    for author_name, idCode in author_entries:
        author_obj = AUTHORS.get(author_name)
        if author_obj:
            try:
                entry = Entry.objects(id_code=idCode.upper()).first()
                if entry:
                    entry.add_author(author_obj)
                    entry.save()

                    # Also create AuthorHasEntry record
                    try:
                        record = AuthorHasEntry(
                            id_author=author_obj,
                            id_code=entry
                        )
                        record.save()
                    except Exception:
                        pass  # Avoid duplicate key errors
            except Exception as e:
                print(f"Error linking author {author_name} to entry {idCode}: {e}")
                continue
except Exception as e:
    print(f"Error linking authors: {e}")
    sys.exit(1)
print("ok")

# Close MongoDB connection
disconnect()
print("Done")
