#!/bin/sh

set -x

# Run pep8 on all .py files in all subfolders

tmpafter=$(mktemp)
find ~/iocage/iocage/cli ~/iocage/iocage/lib -name \*.py -exec flake8 --ignore=E127,E203 {} + > $tmpafter
num_errors_after=`cat $tmpafter | wc -l`
echo $num_errors_after

git checkout HEAD~

tmpbefore=$(mktemp)
find ~/iocage/iocage/cli ~/iocage/iocage/lib -name \*.py -exec flake8 --ignore=E127,E203 {} + > $tmpbefore
num_errors_before=`cat $tmpbefore | wc -l`
echo $num_errors_before


if [ $num_errors_after -gt $num_errors_before ]; then
	echo "New Flake8 errors were introduced:"
	diff -u $tmpbefore $tmpafter
	exit 1
fi
