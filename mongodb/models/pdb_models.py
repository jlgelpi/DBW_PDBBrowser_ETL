"""Models for MongoDB version of PDBBrowser

Contains models for: authors, sources, sequences, entries, and their relationships

Uses mongoengine ODM for object-document mapping and validation.
"""

from mongoengine import (
    Document,
    EmbeddedDocument,
    EmbeddedDocumentListField,
    StringField,
    IntField,
    FloatField,
    ListField,
    ReferenceField,
    DateTimeField,
    ValidationError,
    indexes,
)
from datetime import datetime


class Author(Document):
    """Author document in MongoDB.
    
    Maps from SQL authors table.
    Stores author information with full-text search capability.
    """
    id_author = IntField(primary_key=True, required=True)
    author = StringField(max_length=255)
    
    meta = {
        'collection': 'authors',
        'indexes': [
            ('author', 'text'),  # Full-text index for searching
        ]
    }
    
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
        'collection': 'exp_classes',
    }
    
    def __repr__(self):
        return f"<ExperimentalClass(id={self.id_exp_classe}, classe={self.exp_classe})>"


class CompoundType(Document):
    """Compound type document.
    
    Maps from SQL comptype table.
    Defines types of compounds (e.g., PROTEIN, DNA, RNA, etc).
    """
    id_comp_type = IntField(primary_key=True, required=True)
    type = StringField(max_length=10)
    
    meta = {
        'collection': 'compound_types',
    }
    
    def __repr__(self):
        return f"<CompoundType(id={self.id_comp_type}, type={self.type})>"


class ExperimentalType(Document):
    """Experimental type document.
    
    Maps from SQL expTypes table.
    Stores detailed experimental method types with reference to experimental class.
    """
    id_exp_type = IntField(primary_key=True, required=True)
    id_exp_classe = ReferenceField(ExperimentalClass, field_name='id_exp_classe')
    exp_type = StringField(max_length=255)
    
    meta = {
        'collection': 'exp_types',
        'indexes': [
            'id_exp_classe',
        ]
    }
    
    def __repr__(self):
        return f"<ExperimentalType(id={self.id_exp_type}, type={self.exp_type})>"


class Source(Document):
    """Source document for biological organisms.
    
    Maps from SQL sources table.
    Contains organism information with full-text search capability.
    """
    id_source = IntField(primary_key=True, required=True)
    source = StringField(max_length=255)
    
    meta = {
        'collection': 'sources',
        'indexes': [
            ('source', 'text'),  # Full-text index for searching
        ]
    }
    
    def __repr__(self):
        return f"<Source(id={self.id_source}, source={self.source})>"


class Sequence(EmbeddedDocument):
    """Embedded document for protein/nucleic acid sequences.
    
    Stores sequence information for a specific chain in an entry.
    """
    chain = StringField(max_length=5, required=True)
    sequence = StringField()
    header = StringField()
    
    def __repr__(self):
        return f"<Sequence(chain={self.chain})>"


class Entry(Document):
    """Entry document representing a PDB entry.
    
    Maps from SQL entries table.
    Contains structural biology data with references to related collections.
    """
    id_code = StringField(max_length=4, primary_key=True, required=True)
    id_exp_type = ReferenceField(
        ExperimentalType,
        field_name='id_exp_type',
        null=True
    )
    id_comp_type = ReferenceField(
        CompoundType,
        field_name='id_comp_type',
        null=True
    )
    header = StringField(max_length=255)
    accession_date = StringField(max_length=20)
    compound = StringField(max_length=255)
    resolution = FloatField(null=True)
    sequences = EmbeddedDocumentListField(Sequence)
    authors = ListField(ReferenceField(Author))
    sources = ListField(ReferenceField(Source))
    
    meta = {
        'collection': 'entries',
        'indexes': [
            'id_exp_type',
            'id_comp_type',
            'resolution',
            ('compound', 'text'),  # Full-text index for compound search
            ('header', 'text'),    # Full-text index for header search
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
