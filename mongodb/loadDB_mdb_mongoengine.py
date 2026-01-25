"""Load PDB data into MongoDB using mongoengine ODM models."""

import re
import sys
import os
import argparse
from mongoengine import connect as mongo_connect, disconnect
from mongoengine.errors import ConnectionError

# Add models directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'models'))
from pdb_models import Entry, Author, Source, ExperimentalType, ExperimentalClass, CompoundType, Sequence

# CLI args
parser = argparse.ArgumentParser(description='Load PDB data into MongoDB using mongoengine')
parser.add_argument('-i', '--input_dir', default='.', help='Directory containing input files (default: current dir)')
parser.add_argument('--drop_db', action='store_true', help='Drop all collections before loading')
parser.add_argument('--host', default='localhost', help='MongoDB host (default: localhost)')
parser.add_argument('--port', type=int, default=27017, help='MongoDB port (default: 27017)')
parser.add_argument('--database', default='pdb', help='Database name (default: pdb)')
args = parser.parse_args()
INPUT_DIR = os.path.abspath(args.input_dir)

# Connect to MongoDB
try:
    if os.environ.get("MDB_USERNAME") and os.environ.get("MDB_PASSWORD"):
        user = os.environ["MDB_USERNAME"]
        password = os.environ["MDB_PASSWORD"]
        auth_db = args.database
        mongo_connect(
            db=args.database,
            username=user,
            password=password,
            authSource=auth_db,
            host=args.host,
            port=args.port
        )
    else:
        mongo_connect(db=args.database, host=args.host, port=args.port)
except ConnectionError as e:
    print(f"Error connecting to MongoDB: {str(e)}")
    sys.exit(1)

print(f"Connected to MongoDB at {args.host}:{args.port}, database: {args.database}")

# Drop collections if requested
if args.drop_db:
    print("Dropping existing collections...")
    Entry.drop_collection()
    Author.drop_collection()
    Source.drop_collection()
    ExperimentalType.drop_collection()
    ExperimentalClass.drop_collection()
    CompoundType.drop_collection()

# Create indexes
print("Creating indexes...")
try:
    # Entry indexes
    Entry.ensure_indexes()
    
    # Author indexes
    Author.ensure_indexes()
    
    # Source indexes
    Source.ensure_indexes()
    
    # ExperimentalType indexes
    ExperimentalType.ensure_indexes()
    
    # ExperimentalClass indexes
    ExperimentalClass.ensure_indexes()
    
    # CompoundType indexes
    CompoundType.ensure_indexes()
    
    print("Indexes created successfully.")
except Exception as e:
    print(f"Warning: Error creating indexes: {e}")

# ------------------ Entries ------------------
print("Loading Entries...")
entries_created = 0
exp_types_by_code = {}  # id_code -> expType

try:
    with open(os.path.join(INPUT_DIR, "entries.idx"), 'r') as ENTR:
        for line in ENTR:
            line = line.rstrip()
            if "\t" not in line:
                continue
            fields = line.split("\t")
            if len(fields) < 8:
                continue

            id_code, header, asc_date, compound, source_field, author_list, resol, exp_type_name = fields[:8]

            if len(id_code) != 4:  # TODO Check for new PDB codes.
                continue

            # Parse resolution
            if ',' in str(resol):
                resol = resol.split(",")[0]
            resol_val = None
            if resol != 'NOT':
                try:
                    resol_val = float(resol)
                except ValueError:
                    print(f"Invalid resolution value: '{resol}' for entry {id_code}")

            compound = compound[:255] if compound else ""
            
            id_code = id_code.upper()
            exp_types_by_code[id_code] = exp_type_name

            try:
                entry = Entry(
                    id_code=id_code,
                    header=header,
                    accession_date=asc_date,
                    compound=compound,
                    resolution=resol_val,
                )
                entry.save()
                entries_created += 1
            except Exception as e:
                print(f"Error saving entry {id_code}: {e}")
                continue

except IOError as e:
    print(f"Error reading entries.idx: {str(e)}")
    sys.exit(1)

print(f"Loaded {entries_created} entries.")

# ------------------ ExperimentalClass and CompoundType ------------------
print("Loading Experimental Classes and Compound Types...")
exp_classes = {}  # exp_class_name -> ExperimentalClass
comp_types = {}  # comp_type_name -> CompoundType

try:
    with open(os.path.join(INPUT_DIR, 'pdb_entry_type.txt'), 'r') as EXPCL:
        for line in EXPCL:
            line = line.rstrip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            id_code, comp_type_name, exp_class_name = parts[0], parts[1], parts[2]
            id_code = id_code.upper()

            # Create or get experimental class
            if exp_class_name not in exp_classes:
                try:
                    exp_class = ExperimentalClass(exp_classe=exp_class_name)
                    exp_class.save()
                    exp_classes[exp_class_name] = exp_class
                except Exception as e:
                    print(f"Error saving experimental class {exp_class_name}: {e}")

            # Create or get compound type
            if comp_type_name not in comp_types:
                try:
                    comp_type = CompoundType(comp_type=comp_type_name)
                    comp_type.save()
                    comp_types[comp_type_name] = comp_type
                except Exception as e:
                    print(f"Error saving compound type {comp_type_name}: {e}")

            # Update entry with experimental class and compound type
            try:
                entry = Entry.objects(id_code=id_code).first()
                if entry:
                    if exp_class_name in exp_classes:
                        entry.id_exp_classe = exp_classes[exp_class_name]
                    if comp_type_name in comp_types:
                        entry.id_comp_type = comp_types[comp_type_name]
                    entry.save()
            except Exception as e:
                print(f"Error updating entry {id_code} with experimental class and compound type: {e}")

except IOError as e:
    print(f"Error reading pdb_entry_type.txt: {str(e)}")
    sys.exit(1)

print(f"Loaded {len(exp_classes)} experimental classes and {len(comp_types)} compound types.")

# ------------------ Authors ------------------
print("Loading Authors...")
AUTHORS = {}  # id_code -> [author_names]
IDCODES_WITH_AUTHORS = {}  # author_name -> [id_codes]
AUTHOR_OBJECTS = {}  # author_name -> Author object

try:
    with open(os.path.join(INPUT_DIR, "author.idx"), 'r') as AUTS:
        for line in AUTS:
            line = line.rstrip()
            if ' ; ' not in line:
                continue
            id_code, author_name = line.split(" ; ", 1)
            if not id_code or not author_name:
                continue
            
            if id_code not in AUTHORS:
                AUTHORS[id_code] = []
            AUTHORS[id_code].append(author_name)
            
            if author_name not in IDCODES_WITH_AUTHORS:
                IDCODES_WITH_AUTHORS[author_name] = []
            IDCODES_WITH_AUTHORS[author_name].append(id_code)

    # Update entries with author lists
    for id_code, author_list in AUTHORS.items():
        try:
            entry = Entry.objects(id_code=id_code).first()
            if entry:
                entry.authors = author_list
                entry.save()
        except Exception as e:
            print(f"Error updating authors for entry {id_code}: {e}")

    # Create Author documents
    for author_name, id_code_list in IDCODES_WITH_AUTHORS.items():
        try:
            author = Author(author_name=author_name, id_codes=id_code_list)
            author.save()
            AUTHOR_OBJECTS[author_name] = author
        except Exception as e:
            print(f"Error saving author {author_name}: {e}")

except IOError as e:
    print(f"Error reading author.idx: {str(e)}")
    sys.exit(1)

print(f"Loaded {len(IDCODES_WITH_AUTHORS)} authors.")

# ------------------ Sequences ------------------
print("Loading Sequences...")
header_re = re.compile(r'^>([^_]*)_(.*)mol:(\S*) length:(\S*)')
sequences_added = 0

try:
    with open(os.path.join(INPUT_DIR, "pdb_seqres.txt"), 'r') as SEQS:
        seq = ''
        id_code = ''
        chain = ''
        header = ''
        for line in SEQS:
            line = line.rstrip()
            if line and line[0] == '>':
                if seq and id_code:
                    try:
                        entry = Entry.objects(id_code=id_code.upper()).first()
                        if entry:
                            sequence_obj = Sequence(
                                id_code=id_code.upper(),
                                chain=chain.replace(' ', ''),
                                sequence=seq.replace("\n", ""),
                                header=header
                            )
                            entry.sequences.append(sequence_obj)
                            entry.save()
                            sequences_added += 1
                    except Exception as e:
                        print(f"Error adding sequence for {id_code} chain {chain}: {e}")
                    seq = ''

                groups = header_re.match(line)
                if groups:
                    id_code = groups.group(1)
                    chain = groups.group(2)
                header = line.replace('>', '')
            else:
                seq += line

        # Handle last sequence
        if seq and id_code:
            try:
                entry = Entry.objects(id_code=id_code.upper()).first()
                if entry:
                    sequence_obj = Sequence(
                        id_code=id_code.upper(),
                        chain=chain.replace(' ', ''),
                        sequence=seq.replace("\n", ""),
                        header=header
                    )
                    entry.sequences.append(sequence_obj)
                    entry.save()
                    sequences_added += 1
            except Exception as e:
                print(f"Error adding sequence for {id_code} chain {chain}: {e}")

except IOError as e:
    print(f"Error reading pdb_seqres.txt: {str(e)}")
    sys.exit(1)

print(f"Loaded {sequences_added} sequences.")

# ------------------ Sources ------------------
print("Loading Sources...")
SOURCES = {}  # id_code -> [source strings]
IDCODES_WITH_SOURCES = {}  # source_string -> [id_codes]
SOURCE_OBJECTS = {}  # source_string -> Source object

try:
    with open(os.path.join(INPUT_DIR, "source.idx"), 'r') as SOUR:
        for line in SOUR:
            line = line.rstrip()
            if ' ' not in line:
                continue
            id_code, source_str = line.split(maxsplit=1)
            if not source_str or len(id_code) != 4:
                continue
            id_code = id_code.upper()
            
            if id_code not in SOURCES:
                SOURCES[id_code] = []
            SOURCES[id_code].append(source_str)
            
            if source_str not in IDCODES_WITH_SOURCES:
                IDCODES_WITH_SOURCES[source_str] = []
            IDCODES_WITH_SOURCES[source_str].append(id_code)

    # Update entries with source lists
    for id_code, source_list in SOURCES.items():
        try:
            entry = Entry.objects(id_code=id_code).first()
            if entry:
                entry.sources = source_list
                entry.save()
        except Exception as e:
            print(f"Error updating sources for entry {id_code}: {e}")

    # Create Source documents
    for source_str, id_code_list in IDCODES_WITH_SOURCES.items():
        try:
            source = Source(source_name=source_str, id_codes=id_code_list)
            source.save()
            SOURCE_OBJECTS[source_str] = source
        except Exception as e:
            print(f"Error saving source {source_str}: {e}")

except IOError as e:
    print(f"Error reading source.idx: {str(e)}")
    sys.exit(1)

print(f"Loaded {len(IDCODES_WITH_SOURCES)} sources.")

print("\nData loading completed successfully!")
