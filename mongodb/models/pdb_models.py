"""Models for MongoDB version of PDBBrowser

Contains models for: authors, sources, sequences, entries, and their relationships

Uses mongoengine ODM for object-document mapping and validation.
"""

from mongoengine import *
from datetime import datetime


class Author(Document):
    """Author document in MongoDB.

    Maps from SQL authors table.
    Stores author information with full-text search capability.
    """
    id_author = IntField(primary_key=True, required=True)
    author = StringField(max_length=255)
    entries = ListField(ReferenceField('Entry'))   

    meta = {
        'collection': 'authors',
        'indexes': [
            {'fields': ['$author']},  # Full-text index for searching
        ]
    }

    def add_entry(self, entry):
        """Add an entry reference to this author.

        Args:
            entry: Entry document reference
        """
        if entry not in self.entries:
            self.entries.append(entry)

    def __repr__(self):
        return f"<Author(id={self.id_author}, name={self.author})>"


class ExperimentalClass(Document):
    """Experimental class document.

    Maps from SQL expClasses table.
    Defines categories of experimental techniques (e.g., X-RAY DIFFRACTION, NMR, etc).
    """
    id_exp_classe = IntField(primary_key=True, required=True)
    exp_classe = StringField(max_length=20)

    meta = {
        'collection': 'expClasses',
    }

    def __repr__(self):
        return f"<ExperimentalClass(id={self.id_exp_classe}, classe={self.exp_classe})>"

class CompoundType(Document):
    """Compound type document.

    Maps from SQL comptype table.
    Defines types of compounds (e.g., PROTEIN, DNA, RNA, etc).
    """
    id_comp_type = IntField(primary_key=True, required=True)
    comp_type = StringField(max_length=10)

    meta = {
        'collection': 'compTypes',
    }

    def __repr__(self):
        return f"<CompoundType(id={self.id_comp_type}, type={self.comp_type})>"


class ExperimentalType(Document):
    """Experimental type document.

    Maps from SQL expTypes table.
    Stores detailed experimental method types with reference to experimental class.
    """
    id_exp_type = IntField(primary_key=True, required=True)
    id_exp_classe = ReferenceField(ExperimentalClass, field_name='idExpCclasse')
    expType = StringField(max_length=255)

    meta = {
        'collection': 'expTypes',
        'indexes': [
            'id_exp_classe',
        ]
    }

    def add_exp_class(self, exp_class):
        """Set the experimental class reference.

        Args:
            exp_class: ExperimentalClass document reference
        """
        self.id_exp_classe = exp_class

    def __repr__(self):
        return f"<ExperimentalType(id={self.id_exp_type}, type={self.exp_type})>"


class Source(Document):
    """Source document for biological organisms.

    Maps from SQL sources table.
    Contains organism information with full-text search capability.
    """
    id_source = IntField(primary_key=True, required=True)
    source = StringField(max_length=255)
    entries = ListField(ReferenceField('Entry'))

    meta = {
        'collection': 'sources',
        'indexes': [
            {'fields': ['$source'], 'default_language': 'none'},  # Full-text index for searching
        ]
    }

    def add_entry(self, entry):
        """Add an entry reference to this source.

        Args:
            entry: Entry document reference
        """
        if entry not in self.entries:
            self.entries.append(entry.id_code)

    def __repr__(self):
        return f"<Source(id={self.id_source}, source={self.source})>"


class Sequence(EmbeddedDocument):
    """Embedded document for protein/nucleic acid sequences.

    Stores sequence information for a specific chain in an entry.
    Compound primary key: (id_code, chain)
    """
    id_code = StringField(max_length=4, required=True)
    chain = StringField(max_length=5, required=True)
    sequence = StringField()
    header = StringField()

    meta = {
        'indexes': [
            {'fields': ['id_code', 'chain'], 'unique': True}  # Compound primary key
        ]
    }

    def __repr__(self):
        return f"<Sequence(id_code={self.id_code!r}, chain={self.chain!r})>"


class Entry(Document):
    """Entry document representing a PDB entry.

    Maps from SQL entries table.
    Contains structural biology data with references to related collections.
    """
    id_code = StringField(max_length=4, primary_key=True, required=True)
    id_exp_type = ReferenceDocument(
        ExperimentalType,
        null=True
    )
    id_comp_type = ReferenceDocument(
        CompoundType,
        null=True
    )
    header = StringField(max_length=255)
    accession_date = StringField(max_length=20)
    compound = StringField(max_length=255)
    resolution = FloatField(null=True)
    sequences = EmbeddedDocumentListField(Sequence)
    authors = EmbeddedDocumentListField(Author)
    sources = EmbeddedDocumentListField(Source)

    meta = {
        'collection': 'entries',
        'indexes': [
            'id_exp_type',
            'id_comp_type',
            'resolution',
            {
                'fields': ['$compound', '$header', '$sequences.header','$authors.author', '$sources.source'], 
                'default_language': 'none'
            },  # Full-text index for compound and header search
        ]
    }

    def __repr__(self):
        return f"<Entry(id={self.id_code}, resolution={self.resolution})>"

    def add_sequence(self, chain, sequence, header=None):
        """Add a sequence to this entry.

        Args:
            chain: Chain identifier
            sequence: The actual sequence string
            header: Optional sequence header information
        """
        seq = Sequence(chain=chain, sequence=sequence, header=header)
        self.sequences.append(seq)

    def add_author(self, author):
        """Add an author reference to this entry.

        Args:
            author: Author document reference
        """
        if author not in self.authors:
            self.authors.append(author)

    def add_source(self, source):
        """Add a source reference to this entry.

        Args:
            source: Source document reference
        """
        if source not in self.sources:
            self.sources.append(source)
