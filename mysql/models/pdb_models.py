"""SQLAlchemy ORM models generated from PDBBrowser_struc_sqldump.sql

Contains models for: author, author_has_entry (association), comptype, entry,
entry_has_source, expClasse, expType, sequence, source.

Usage example:
    from sqlalchemy import create_engine
    from models.pdb_models import Base
    engine = create_engine('mysql+pymysql://user:pass@host/pdb')
    Base.metadata.create_all(engine)
"""
from sqlalchemy import (
    Column, Integer, String, Float, Text, ForeignKey, Table
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

# association table for many-to-many Author <-> Entry
author_entry_table = Table(
    'author_has_entry', Base.metadata,
    Column('idAuthor', Integer, ForeignKey('authors.idAuthor'), primary_key=True),
    Column('idCode', String(4), ForeignKey('entries.idCode'), primary_key=True),
)

# association table for many-to-many Entry <-> Source (was entry_has_source)
entry_source_table = Table(
    'entry_has_source', Base.metadata,
    Column('idCode', String(4), ForeignKey('entries.idCode'), primary_key=True),
    Column('idSource', Integer, ForeignKey('sources.idSource'), primary_key=True),
)

class Author(Base):
    ''' Author model representing the 'authors' table.'''
    __tablename__ = 'authors'
    idAuthor = Column(Integer, primary_key=True, autoincrement=True)
    author = Column(String(255))

    entries = relationship('Entry', secondary=author_entry_table, back_populates='authors')

    def __repr__(self):
        return f"<Author(idAuthor={self.idAuthor!r}, author={self.author!r})>"

class CompType(Base):
    ''' CompType model representing the 'compTypes' table. Types of compounds (prot, nuc, ...) '''
    __tablename__ = 'compTypes'
    idCompType = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String(10))

    entries = relationship('Entry', back_populates='compTypes')

    def __repr__(self):
        return f"<CompType (idCompType={self.idCompType!r}, type={self.type!r})>"

class ExpClasse(Base):
    ''' ExpClasse model representing the 'expClasses' table. Experimental classes (X-ray, NMR, ...) '''
    __tablename__ = 'expClasses'
    idExpClasse = Column(Integer, primary_key=True, autoincrement=True)
    expClasse = Column(String(20))

    expTypes = relationship('ExpType', back_populates='expClasses')

    def __repr__(self):
        return f"<ExpClasse(idExpClasse={self.idExpClasse!r}, expClasse={self.expClasse!r})>"

class ExpType(Base):
    ''' ExpType model representing the 'expTypes' table. Verbose Experimental types (X-ray diffraction, solution NMR, ...) '''
    __tablename__ = 'expTypes'
    idExpType = Column(Integer, primary_key=True, autoincrement=True)
    idExpClasse = Column(Integer, ForeignKey('expClasses.idExpClasse'))
    ExpType = Column(String(255))

    expClasses = relationship('ExpClasse', back_populates='expTypes')
    entries = relationship('Entry', back_populates='expTypes')

    def __repr__(self):
        return f"<ExpType(idExpType={self.idExpType!r}, ExpType={self.ExpType!r})>"

class Entry(Base):
    ''' Main table representing PDB entries.'''
    __tablename__ = 'entries'
    idCode = Column(String(4), primary_key=True)
    idExpType = Column(Integer, ForeignKey('expTypes.idExpType'))
    idCompType = Column(Integer, ForeignKey('compTypes.idCompType'))
    header = Column(String(255))
    accessionDate = Column(String(20))
    compound = Column(String(255))
    resolution = Column(Float)

    authors = relationship('Author', secondary=author_entry_table, back_populates='entries')
    sources = relationship('Source', secondary=entry_source_table, back_populates='entries')

    compTypes = relationship('CompType', back_populates='entries')
    expTypes = relationship('ExpType', back_populates='entries')
    sequences = relationship('Sequence', back_populates='entry', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Entry(idCode={self.idCode!r}, header={self.header!r})>"

class Sequence(Base):
    ''' Table representing sequences associated with PDB chain entries.'''
    __tablename__ = 'sequences'
    idCode = Column(String(4), ForeignKey('entries.idCode'), primary_key=True)
    chain = Column(String(5, collation='utf8_bin'), primary_key=True) # force case sensitivity
    sequence = Column(Text)
    header = Column(Text)

    entry = relationship('Entry', back_populates='sequences')

    def __repr__(self):
        return f"<Sequence(idCode={self.idCode!r}, chain={self.chain!r})>"

class Source(Base):
    ''' Table representing sources associated with PDB entries.'''
    __tablename__ = 'sources'
    idSource = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(255))

    # many-to-many to Entry via association table
    entries = relationship('Entry', secondary=entry_source_table, back_populates='sources')

    def __repr__(self):
        return f"<Source(idSource={self.idSource!r}, source={self.source!r})>"
