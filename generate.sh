#!/usr/bin/env bash

set -euo pipefail

if [[ $# -eq 0 ]]; then
  versions=(5.36.1)
else
  versions=("$@")
fi

function Cleanup {
  if [[ "${tmpdir:+1}" == 1 ]]; then rm -rf "$tmpdir"; fi
}
trap Cleanup EXIT

script_dir=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
tmpdir=$(mktemp -d)
export PERL5LIB="$tmpdir/perl5/lib/perl5"
export PERL_MM_OPT="INSTALL_BASE=$tmpdir/perl5"
export PATH="$tmpdir/perl5/bin:/usr/bin/vendor_perl:$PATH"
export MAKEFLAGS='-j4'

cd $tmpdir
git clone https://github.com/Grinnz/perldoc-browser.git
cd perldoc-browser

cpanm -n --local-lib="$tmpdir/perl5" --installdeps .
./perldoc-browser.pl install "${versions[@]}"
python3 "$script_dir/generate.py" "${versions[@]}"

cd "$script_dir"
