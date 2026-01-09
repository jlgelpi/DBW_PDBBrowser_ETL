#!/usr/bin/perl
use DBI;
use strict;
#
require "bdconn.pl";
my $idCode= $ARGV[0];
my $dbh=connectDB();
#
my $dataEntry = $dbh->selectrow_hashref(
"SELECT * FROM 
Entry e, 
ExpType exp, 
expClasse expc,
source s,
Entry_has_source es
WHERE 
e.idCode='$idCode' and 
e.idExpType=exp.idExpType and 
exp.expClasse_idExpClasse = expc.idExpClasse and
e.idCode = es.idCode and s.idsource = es.idsource
");
foreach my $f (keys(%{$dataEntry})) {
print "$f\t$dataEntry->{$f}\n";
}
