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
my $TMP_DIR = Utils::get_tmp_dir();
system("mkdir -p $TMP_DIR");

# Set up project
my $project = Project::create_project($PID);
$project->{prog_root} = $TMP_DIR;

# Get database handle for results
my $dbh = DB::get_db_handle($TAB_REV_PAIRS, $db_dir);
my @COLS = DB::get_tab_columns($TAB_REV_PAIRS) or die;

# Figure out which IDs to run script for
my @ids = $project->get_bug_ids();
# if (defined $BID) {
#     if ($BID =~ /(\d+):(\d+)/) {
#         @ids = grep { ($1 <= $_) && ($_ <= $2) } @ids;
#     } else {
#         # single vid
#         @ids = grep { ($BID == $_) } @ids;
#     }
# }

# if (defined $BI) {
	printf("defined BI: %s \n", $BI);
	if ($BI =~ /^\d+$/) {
		@ids = grep { ($BI == $_) } @ids;
	}
# }
print "@ids\n";

my $sth = $dbh->prepare("SELECT * FROM $TAB_REV_PAIRS WHERE $PROJECT=? AND $ID=?") or die $dbh->errstr;
foreach my $bid (@ids) {
    printf ("%4d: $project->{prog_name}\n", $bid);

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
    _check_t2v2($project, $bid, \%data) or next;

    # Add data set to result file
    _add_row(\%data);
}
$dbh->disconnect();
system("rm -rf $TMP_DIR");

#
# Check size of src diff, which is created by initialize-revisions.pl script,
# for a given candidate bug (bid).
#
# Returns 1 on success, 0 otherwise
#
sub _check_diff {
    my ($project, $bid, $data) = @_;

    # Determine patch size for src and test patches (rev2 -> rev1)
    my $patch_test = "$PATCHES_DIR/$bid.test.patch";
    my $patch_src = "$PATCHES_DIR/$bid.src.patch";

    if (!(-e $patch_test) || (-z $patch_test)) {
        $data->{$DIFF_TEST} = 0;
    } else {
        my $diff = _read_file($patch_test);
        die unless defined $diff;
        $data->{$DIFF_TEST} = scalar(split("\n", $diff));
    }

    if (-z $patch_src) {
        $data->{$DIFF_SRC} = 0;
        return 0;
    } else {
        my $diff = _read_file($patch_src);
        die unless defined $diff;
        $data->{$DIFF_SRC} = scalar(split("\n", $diff)) or return 0;
    }

    return 1;
}

#
# Check whether v2 and t2 can be compiled and export failing tests.
#
# Returns 1 on success, 0 otherwise
#
sub _check_t2v2 {
    my ($project, $bid, $data) = @_;

    # Lookup revision ids
    my $v1 = $project->lookup("${bid}b");
    my $v2 = $project->lookup("${bid}f");

    # Clean previous results
    `>$FAILING_DIR/$v2` if -e "$FAILING_DIR/$v2";

    # Checkout v2
    $project->checkout_vid("${bid}f", $TMP_DIR, 1) == 1 or die;

    # Compile v2 ant t2
	system("cd tracing && python Tracer.py $project->{prog_root} full $PROJECTS_DIR/$PID fix_build 2>&1");
	my $compile_cmd = " cd $project->{prog_root}" .
					  " ant -q -f $D4J_BUILD_FILE -Dd4j.home=$BASE_DIR -Dd4j.dir.projects=$PROJECTS_DIR -Dbasedir=$project->{prog_root}  -Dbuild.compiler=javac1.8  compile 2>&1";
	my $compile_tests_cmd = " cd $project->{prog_root}" .
					  " ant -q -f $D4J_BUILD_FILE -Dd4j.home=$BASE_DIR -Dd4j.dir.projects=$PROJECTS_DIR -Dbasedir=$project->{prog_root}  -Dbuild.compiler=javac1.8 compile-tests 2>&1";
	my $compile_tests_cmd_log = " cd $project->{prog_root}" .
					  " ant -q -f $D4J_BUILD_FILE -Dd4j.home=$BASE_DIR -Dd4j.dir.projects=$PROJECTS_DIR -Dbasedir=$project->{prog_root}  -Dbuild.compiler=javac1.8 compile-tests 2>&1 >> $WORK_DIR/compile_tests_log.log";
	my $run_tests_log_cmd_1 = " cd $project->{prog_root}" .
					  " ant -q -f $D4J_BUILD_FILE -Dd4j.home=$BASE_DIR -Dd4j.dir.projects=$PROJECTS_DIR -Dbasedir=$project->{prog_root}  -Dbuild.compiler=javac1.8 -DOUTFILE=$WORK_DIR/failing_tests.log  run.dev.tests 2>&1 >> $WORK_DIR/failing_tests_logger.log";
	my $run_tests_log_cmd_2 = " cd $project->{prog_root}" .
					  " ant -q -f $D4J_BUILD_FILE -Dd4j.home=$BASE_DIR -Dd4j.dir.projects=$PROJECTS_DIR -Dbasedir=$project->{prog_root}  -Dbuild.compiler=javac1.8 -DOUTFILE=$WORK_DIR/failing_tests_after_fix.log  run.dev.tests 2>&1 >> $WORK_DIR/failing_tests_logger_after_fix.log";
	my $run_tests_log_cmd_3 = " cd $project->{prog_root}" .
					  " ant -q -f $D4J_BUILD_FILE -Dd4j.home=$BASE_DIR -Dd4j.dir.projects=$PROJECTS_DIR -Dbasedir=$project->{prog_root}  -Dbuild.compiler=javac1.8 -DOUTFILE=$project->{prog_root}/v2.fail  run.dev.tests 2>&1 >>$WORK_DIR/run_tests_log.log";
    # my $ret = $project->compile();
    my $ret = Utils::exec_cmd($compile_cmd, "Running ant compile cmd ()");
	_add_bool_result($data, $COMP_V2, $ret) or return 0;
    # $project->compile_tests("$WORK_DIR/compile_tests_log.log");
    Utils::exec_cmd($compile_tests_cmd_log, "Running ant compile compile_tests_cmd_log ()");

	system("python fix_compile_errors.py $WORK_DIR/compile_tests_log.log $project->{prog_root} 2>&1");
    # $ret = $project->compile_tests();
    $ret = Utils::exec_cmd($compile_tests_cmd, "Running ant compile cmd ()");
	$project->fix_tests("${bid}f");
	# $project->run_tests_and_log($file2, "$WORK_DIR/failing_tests_logger.log");
    Utils::exec_cmd($run_tests_log_cmd_1, "Running ant compile cmd ()");

	system("python fix_compile_errors.py $WORK_DIR/compile_tests_log.log $project->{prog_root} 2>&1");
	# $project->run_tests_and_log($file3, "$WORK_DIR/failing_tests_logger_after_fix.log");
    Utils::exec_cmd($run_tests_log_cmd_2, "Running ant compile cmd ()");


    _add_bool_result($data, $COMP_T2V2, $ret) or return 0;

    my $successful_runs = 0;
    my $run = 1;
    while ($successful_runs < $TEST_RUNS && $run <= $MAX_TEST_RUNS) {
        # Automatically fix broken tests and recompile
        $project->fix_tests("${bid}f");
        # $project->compile_tests() or die;
        Utils::exec_cmd($compile_tests_cmd, "Running ant compile cmd ()") or die;

        # Run t2 and get number of failing tests
        my $file = "$project->{prog_root}/v2.fail"; `>$file`;
        # $project->run_tests_and_log($file, "$WORK_DIR/run_tests_log.log") or last;
		Utils::exec_cmd($run_tests_log_cmd_3, "Running ant compile cmd ()") or last;


        # Filter out invalid test names, such as testEncode[0].
        # This problem impacts many Commons projects.
        if(-e "$project->{prog_root}/v2.fail"){
            rename("$project->{prog_root}/v2.fail", "$project->{prog_root}/v2.fail".'.bak');
            open(IN, '<'."$project->{prog_root}/v2.fail".'.bak') or die $!;
            open(OUT, '>'."$project->{prog_root}/v2.fail") or die $!;
            while(<IN>) {
                if($_ =~ /\-\-\-/){
                    $_ =~ s/\[[0-9]\]//g;
                }
                print OUT $_;
            }
            close(IN);
            close(OUT);
        }
	
        # Get number of failing tests
        my $list = Utils::get_failing_tests($file);
        my $fail = scalar(@{$list->{"classes"}}) + scalar(@{$list->{"methods"}});

        if ($run == 1) {
            $data->{$FAIL_T2V2} = $fail;
        } else {
            $data->{$FAIL_T2V2} += $fail;
        }

        ++$successful_runs;

        # Append to log if there were (new) failing tests
        unless ($fail == 0) {
            open(OUT, ">>$FAILING_DIR/$v2") or die "Cannot write failing tests: $!";
            print OUT "## $project->{prog_name}: $v2 ##\n";
            close OUT;
            system("cat $file >> $FAILING_DIR/$v2");
            $successful_runs = 0;
        }
        ++$run;
    }
    return 1;
}

#
# Check whether t2 and v1 can be compiled
#
sub _check_t2v1 {
    my ($project, $bid, $data) = @_;

    # Lookup revision ids
    # my $v1  = $project->lookup("${bid}b");
    # my $v2  = $project->lookup("${bid}f");

    # Checkout v1
    # $project->checkout_vid("${bid}b", $TMP_DIR, 1) == 1 or die;

    # Compile v1 and t2v1
	# system("cd tracing && python Tracer.py $project->{prog_root} full $PROJECTS_DIR/$PID fix_build 2>&1");
    # my $ret = $project->compile();
	# $project->compile_tests("$WORK_DIR/compile_tests_a2_log.log");
	# system("python fix_compile_errors.py $WORK_DIR/compile_tests_a2_log.log $project->{prog_root} 2>&1");
	# $ret = $project->compile_tests();
    _add_bool_result($data, $COMP_V1, 1);
    _add_bool_result($data, $COMP_T2V1, 1);
}

#
# Read a file line by line and return an array with all lines.
#
sub _read_file {
    my $fn = shift;
    printf("read_file:\n");
    printf("read_file: %s\n", $fn);
	open(FH, "<$fn") or confess "Could not open file: $!";
    my @lines = <FH>;
    close(FH);
    return join('', @lines);
}

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
