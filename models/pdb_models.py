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
    Column('idAuthor', Integer, ForeignKey('author.idAuthor'), primary_key=True),
    Column('idCode', String(4), ForeignKey('entry.idCode'), primary_key=True),
)

# association table for many-to-many Entry <-> Source (was entry_has_source)
entry_source_table = Table(
    'entry_has_source', Base.metadata,
    Column('idCode', String(4), ForeignKey('entry.idCode'), primary_key=True),
    Column('idSource', Integer, ForeignKey('source.idSource'), primary_key=True),
)

class Author(Base):
    __tablename__ = 'author'
    idAuthor = Column(Integer, primary_key=True, autoincrement=True)
    author = Column(String(255))

    entries = relationship('Entry', secondary=author_entry_table, back_populates='authors')

    def __repr__(self):
        return f"<Author(idAuthor={self.idAuthor!r}, author={self.author!r})>"

class CompType(Base):
    __tablename__ = 'comptype'
    idCompType = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String(10))

    entries = relationship('Entry', back_populates='comptype')

    def __repr__(self):
        return f"<CompType(idCompType={self.idCompType!r}, type={self.type!r})>"

class ExpClasse(Base):
    __tablename__ = 'expClasse'
    idExpClasse = Column(Integer, primary_key=True, autoincrement=True)
    expClasse = Column(String(20))

    expTypes = relationship('ExpType', back_populates='expClasse')

    def __repr__(self):
        return f"<ExpClasse(idExpClasse={self.idExpClasse!r}, expClasse={self.expClasse!r})>"

class ExpType(Base):
    __tablename__ = 'expType'
    idExpType = Column(Integer, primary_key=True, autoincrement=True)
    idExpClasse = Column(Integer, ForeignKey('expClasse.idExpClasse'))
    ExpType = Column(String(255))

    expClasse = relationship('ExpClasse', back_populates='expTypes')
    entries = relationship('Entry', back_populates='expType')

    def __repr__(self):
        return f"<ExpType(idExpType={self.idExpType!r}, ExpType={self.ExpType!r})>"

class Entry(Base):
    __tablename__ = 'entry'
    idCode = Column(String(4), primary_key=True)
    idExpType = Column(Integer, ForeignKey('expType.idExpType'))
    idCompType = Column(Integer, ForeignKey('comptype.idCompType'))
    header = Column(String(255))
    ascessionDate = Column(String(20))
    compound = Column(String(255))
    resolution = Column(Float)

    authors = relationship('Author', secondary=author_entry_table, back_populates='entries')
    comptype = relationship('CompType', back_populates='entries')
    expType = relationship('ExpType', back_populates='entries')
    sequences = relationship('Sequence', back_populates='entry', cascade='all, delete-orphan')
    # many-to-many to Source via association table
    sources = relationship('Source', secondary=entry_source_table, back_populates='entries')

    def __repr__(self):
        return f"<Entry(idCode={self.idCode!r}, header={self.header!r})>"

class Sequence(Base):
    __tablename__ = 'sequence'
    idCode = Column(String(4), ForeignKey('entry.idCode'), primary_key=True)
    chain = Column(String(5), primary_key=True)
    sequence = Column(Text)
    header = Column(Text)

    entry = relationship('Entry', back_populates='sequences')

    def __repr__(self):
        return f"<Sequence(idCode={self.idCode!r}, chain={self.chain!r})>"

class Source(Base):
    __tablename__ = 'source'
    idSource = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(255))

    # many-to-many to Entry via association table
    entries = relationship('Entry', secondary=entry_source_table, back_populates='sources')

    def __repr__(self):
        return f"<Source(idSource={self.idSource!r}, source={self.source!r})>"
