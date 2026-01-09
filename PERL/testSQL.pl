#!/usr/bin/perl
use DBI;
use strict;
use Data::Dumper;
require "bdconn.pl";
#
print "Simple SQL tester, type exit to finish\n";
my $dbh=connectDB() || die $DBI::errstr;
my $sql="";
while (<>) {
	chomp;
	if (/exit/) {exit};
	if (!/^([^;]*);/) {
		$sql.="$_ "
	} else {
		$sql.="$1;";		
		my $res = execSQL ($dbh,$sql);
		print $res;
		print "\n";	
		$sql="";
	}
}

sub execSQL {
	my ($dbh,$sql) = @_;
	print "\n$sql\n";
	if ($sql =~ /(SELECT|SHOW)/i) {
		my $res="";
		my $sth=$dbh->prepare($sql);
		$sth->execute();
		my $head=0;
		my $line="";
		while (my $row = $sth->fetchrow_hashref) {
			if (!$head) {
			 $head = "| ".join(" | ", keys(%$row))." |";
			 $line = "-" x length($head);
			 $res .= "$head\n$line\n";
			}
			$res .= "| ".join(" | ", values(%$row))." |\n";
		}
		$res.="$line\n";
		return $res;
	} else {
		return $dbh->do($sql);
	}
}			
		
		
	
	
