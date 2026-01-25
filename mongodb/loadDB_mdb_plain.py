"""Load PDB data into MongoDB using mongoengine ODM models."""

import re
from sqlite3 import connect
import sys
import os
import argparse
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

# CLI args
parser = argparse.ArgumentParser(description='Load PDB data into MongoDB')
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
        authDB = args.database
        client = MongoClient(
            f"mongodb://'{user}:{password}@{host}/{authDB}"
        )
        db = client[args.database]
    else:
        client = MongoClient(host=args.host, port=args.port)
        db = client[args.database]
         
except Exception as e:
    print(f"Error connecting to MongoDB: {str(e)}")
    sys.exit(1)

print(f"Connected to MongoDB at {args.host}:{args.port}, database: {args.database}")

# ------------------ Entries ------------------
print("Loading Entries...")
entries_created = 0
expTypesByCode = {}  # id_code -> (expType, expClassName)

entries_collection = db['entries']
authors_collection = db['authors']
sources_collection = db['sources']  
exp_types_collection = db['exp_types']
exp_classes_collection = db['exp_classes']
comp_types_collection = db['comp_types']

if args.drop_db:
    print("Dropping existing collections...")
    entries_collection.drop()
    authors_collection.drop()
    exp_types_collection.drop()
    exp_classes_collection.drop()
    comp_types_collection.drop()
    sources_collection.drop()
    # Recreate indexes if needed
    entries_collection.create_index("resolution")
    entries_collection.create_index("experiment_type")
    entries_collection.create_index("experimental_class")
    entries_collection.create_index("compound_type")
    entries_collection.create_index("sources")
    entries_collection.create_index([
        ("compound", "text"), 
        ("header", "text"), 
        ("sequences.header", "text"), 
        ("authors", "text"), 
        ("sources", "text")
        ], default_language='none'
    )
try:
    with open(os.path.join(INPUT_DIR, "entries.idx"), 'r') as ENTR:
        for line in ENTR:
            line = line.rstrip()
            if "\t" not in line:
                continue
            fields = line.split("\t")
            if len(fields) < 8:
                continue

            id_code, header, ascDate, compound, source_field, authorList, resol, expTypeName = fields[:8]

            if len(id_code) != 4: # TODO Check for new PDB codes. 
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
            # Get references
            exp_type = expTypeName
                    
            try:
                entries_collection.insert_one({
                    "_id": id_code,
                    "header": header,
                    "accession_date": ascDate,
                    "compound": compound,
                    "resolution": resol_val,
                    "experiment_type": exp_type
                })
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
exp_classes = set()
comp_types = set()
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

            exp_classes.add(exp_class_name)
            comp_types.add(comp_type_name)
            # Update entry with experimental class and compound type
            try:
                entries_collection.update_one(
                    {"_id": id_code},
                    {"$set": {
                        "experimental_class": exp_class_name,
                        "compound_type": comp_type_name
                    }}
                )
            except Exception as e:
                print(f"Error updating entry {id_code} with experimental class and compound type: {e}")
            
except IOError as e:
    print(f"Error reading pdb_entry_type.txt: {str(e)}")
    sys.exit(1)

for exp_class in exp_classes:
    try:
        exp_classes_collection.insert_one( {"exp_class_name": exp_class} )
    except Exception as e:
        print(f"Error saving experimental class {exp_class}: {e}")
for comp_type in comp_types:
    try:
        comp_types_collection.insert_one( {"comp_type_name": comp_type} )
    except Exception as e:
        print(f"Error saving compound type {comp_type}: {e}")       
print(f"Loaded {len(exp_classes)} experimental classes and {len(comp_types)} compound types.")
# ------------------ Authors ------------------
print("Loading Authors...")
AUTHORS = {}
IDCODES_WITH_AUTHORS = {}
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
    for id_code, author_list in AUTHORS.items():
        try:
            entries_collection.update_one(
                {"_id": id_code},
                {"$set": {"authors": author_list}}
            )
        except Exception as e:
            print(f"Error updating authors for entry {id_code}: {e}")
    for author_name, id_code_list in IDCODES_WITH_AUTHORS.items():
        try:
            authors_collection.insert_one(
                {"author_name": author_name, "idCodes": id_code_list}    
            )
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
                        entries_collection.update_one(
                            {"_id": id_code .upper()},
                            {"$push": {
                                "sequences": {
                                    "chain": chain.replace(' ', ''),
                                    "sequence": seq.replace("\n", ""),
                                    "header": header
                                }
                            }}
                        )
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
                entries_collection.update_one(
                    {"_id": id_code.upper()},
                    {"$push": {
                        "sequences": {
                            "chain": chain.replace(' ', ''),
                            "sequence": seq.replace("\n", ""),
                            "header": header
                        }
                    }}
                )
                sequences_added += 1
            except Exception as e:
                print(f"Error adding sequence for {id_code} chain {chain}: {e}")
        
except IOError as e:
    print(f"Error reading pdb_seqres.txt: {str(e)}")
    sys.exit(1)
print(f"Loaded {sequences_added} sequences.")
# ------------------ Sources ------------------

print("Loading Sources...")
SOURCES = {}  # source string -> Source instance
IDCODES_WITH_SOURCES = {}
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
                SOURCES[id_code]= []
            SOURCES[id_code].append(source_str)
            if source_str not in IDCODES_WITH_SOURCES:
                IDCODES_WITH_SOURCES[source_str] = []
            IDCODES_WITH_SOURCES[source_str].append(id_code)
    for id_code, source_list in SOURCES.items():
        try:
            entries_collection.update_one(
                {"_id": id_code},
                {"$set": {"sources": source_list}}
            )            
        except Exception as e:
            print(f"Error updating sources for entry {id_code}: {e}")            
    for source_str, id_code_list in IDCODES_WITH_SOURCES.items():
        try:
            sources_collection.insert_one(
                {"source_name": source_str, "idCodes": id_code_list}    
            )
        except Exception as e:
            print(f"Error saving source {source_str}: {e}")
except IOError as e:
    print(f"Error reading source.idx: {str(e)}")
    sys.exit(1)
print(f"Loaded {len(IDCODES_WITH_SOURCES)} sources.")





