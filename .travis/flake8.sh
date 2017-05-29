#!/bin/sh
# Run pep8 on all .py files in all subfolders

tmpafter=$(mktemp)
find ./iocage/cli ./iocage/lib -name \*.py -exec flake8 --ignore=E127,E203 {} + > $tmpafter
num_errors_after=`cat $tmpafter | wc -l`
echo "Current Error Count: ${num_errors_after}"

# Get new tags from remote
git fetch --tags
# Get latest tag name
last_release=$(git describe --tags `git rev-list --tags --max-count=1`)

echo "Comparing with last stable release: ${last_release}"
git checkout ${last_release}

tmpbefore=$(mktemp)
find ./iocage/cli ./iocage/lib -name \*.py -exec flake8 --ignore=E127,E203 {} + > $tmpbefore
num_errors_before=`cat $tmpbefore | wc -l`
echo "${last_release}'s Error Count: ${num_errors_before}"


if [ $num_errors_after -gt $num_errors_before ]; then
	echo "New Flake8 errors were introduced:"
	diff -u $tmpbefore $tmpafter
	exit 1
fi
