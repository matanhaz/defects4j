#!/usr/bin/env perl
#
#-------------------------------------------------------------------------------
# Copyright (c) 2014-2019 René Just, Darioush Jalali, and Defects4J contributors.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#-------------------------------------------------------------------------------

=pod

=head1 NAME

analyze-project.pl -- Determine all suitable candidates listed in the active-bugs csv.

=head1 SYNOPSIS

analyze-project.pl -p project_id -w work_dir -g tracker_name -t tracker_project_id [-b bug_id] [-i bug_index]

=head1 OPTIONS

=over 4

=item B<-p C<project_id>>

The id of the project for which the version pairs are analyzed.

=item B<-w C<work_dir>>

The working directory used for the bug-mining process.

=item B<-g C<tracker_name>>

The source control tracker name, e.g., jira, github, google, or sourceforge.

=item B<-t C<tracker_project_id>>

The name used on the issue tracker to identify the project. Note that this might
not be the same as the Defects4j project name / id, for instance, for the
commons-lang project is LANG.

=item B<-b C<bug_id>>

Only analyze this bug id. The bug_id has to follow the format B<(\d+)(:(\d+))?>.
Per default all bug ids, listed in the active-bugs csv, are considered.

=item B<-i C<bug_index>>

Only analyze this bug id by index. The bug_id has to follow the format B<(\d+)(:(\d+))?>.
Per default all bug ids, listed in the active-bugs csv, are considered.

=back

=head1 DESCRIPTION

Runs the following worflow for all candidate bugs in the project's C<active-bugs.csv>,
or (if -b is specified) for a subset of candidates:

=over 4

=item 1) Verify that src diff (between pre-fix and post-fix) is not empty.

=item 3) Checkout fixed revision.

=item 4) Compile src and test.

=item 5) Run tests and log failing tests to F<C<PROJECTS_DIR>/<PID>/failing_tests>.

=item 6) Exclude failing tests, recompile and rerun. This is repeated until
         there are no more failing tests in F<$TEST_RUNS> consecutive
         executions. (Maximum limit of looping in this phase is specified by
         F<$MAX_TEST_RUNS>).

=item 7) Checkout fixed version.

=item 8) Apply src patch (fixed -> buggy).

=item 9) Compile src and test.

=back

The result for each individual step is stored in F<C<work_dir>/$TAB_REV_PAIRS>.
For each steps the output table contains a column, indicating the result of the
the step or '-' if the step was not applicable.

=cut
use warnings;
use strict;
use File::Basename;
use Cwd qw(abs_path);
use Getopt::Std;
use Pod::Usage;
use Carp qw(confess);

use lib (dirname(abs_path(__FILE__)) . "/../core/");
use Constants;
use Project;
use DB;
use Utils;

my %cmd_opts;
getopts('p:w:g:t:b:i:', \%cmd_opts) or pod2usage(1);

pod2usage(1) unless defined $cmd_opts{p} and defined $cmd_opts{w}
                    and defined $cmd_opts{g} and defined $cmd_opts{t};

my $PID = $cmd_opts{p};
my $BID = $cmd_opts{b};
my $BI = $cmd_opts{i};
my $WORK_DIR = abs_path($cmd_opts{w});
my $TRACKER_ID = $cmd_opts{t};
my $TRACKER_NAME = $cmd_opts{g};

# Check format of target version id
# if (defined $BID) {
#     $BID =~ /^(\d+)(:(\d+))?$/ or die "Wrong version id format ((\\d+)(:(\\d+))?): $BID!";
# }

# Add script and core directory to @INC
unshift(@INC, "$WORK_DIR/framework/core");

# Override global constants
$REPO_DIR = "$WORK_DIR/project_repos";
$PROJECTS_DIR = "$WORK_DIR/framework/projects";

# Set the projects and repository directories to the current working directory
my $PATCHES_DIR = "$PROJECTS_DIR/$PID/patches";
my $FAILING_DIR = "$PROJECTS_DIR/$PID/failing_tests";

-d $PATCHES_DIR or die "$PATCHES_DIR does not exist: $!";
-d $FAILING_DIR or die "$FAILING_DIR does not exist: $!";

# DB_CSVs directory
my $db_dir = $WORK_DIR;

# Number of successful test runs in a row required
my $TEST_RUNS = 2;
# Number of maximum test runs (give up point)
my $MAX_TEST_RUNS = 3;

# Temporary directory

# Set up project
my $project = Project::create_project($PID);
# $project->{prog_root} = $TMP_DIR;

# Get database handle for results
my $dbh = DB::get_db_handle($TAB_REV_PAIRS, $db_dir);
my @COLS = DB::get_tab_columns($TAB_REV_PAIRS) or die;

# Figure out which IDs to run script for
# if (defined $BID) {
#     if ($BID =~ /(\d+):(\d+)/) {
#         @ids = grep { ($1 <= $_) && ($_ <= $2) } @ids;
#     } else {
#         # single vid
#         @ids = grep { ($BID == $_) } @ids;
#     }
# }
my @ids = grep { ($BI == $_) } $project->get_bug_ids();

# my $sth = $dbh->prepare("SELECT * FROM $TAB_REV_PAIRS WHERE $PROJECT=? AND $ID=?") or die $dbh->errstr;
foreach my $bid (@ids) {

    # Skip existing entries
    # $sth->execute($PID, $bid);
    # if ($sth->rows !=0) {
    #     printf("      -> Skipping (existing entry in $TAB_REV_PAIRS)\n");
    #     next;
    # }

    my %data;
    $data{$PROJECT} = $PID;
    $data{$ID} = $bid;
    $data{$ISSUE_TRACKER_NAME} = $TRACKER_NAME;
    $data{$ISSUE_TRACKER_ID} = $TRACKER_ID;

    # _check_diff($project, $bid, \%data) and
	_add_bool_result(\%data, $COMP_V1, 1);
    _add_bool_result(\%data, $COMP_T2V1, 1);
	_add_bool_result(\%data, $COMP_T2V2, 1);
    # _check_t2v2($project, $bid, \%data) or next;

    # Add data set to result file
    _add_row(\%data);
}
$dbh->disconnect();


#
# Insert boolean success into hash
#
sub _add_bool_result {
    my ($data, $key, $success) = @_;
    $data->{$key} = $success;
}

#
# Add a row to the database table

sub _add_row {
    my $data = shift;

    my @tmp;
    foreach (@COLS) {
        push (@tmp, $dbh->quote((defined $data->{$_} ? $data->{$_} : "-")));
    }

    my $row = join(",", @tmp);
    $dbh->do("INSERT INTO $TAB_REV_PAIRS VALUES ($row)");
}

=pod

=head1 SEE ALSO

Previous step in workflow: Manually verify that all test failures
(failing_tests) are valid and not spurious, broken, random, or due to classpath
issues.

Next step in workflow: F<get-trigger.pl>.

=cut
