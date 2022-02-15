# perldoc-html-generator

A simple script to generate offline HTML perldoc archive from [perldoc-browser](https://github.com/Grinnz/perldoc-browser).

### Example Usages

`generate.sh` will generate a tar.xz file with docs of all given versions.

```
./generate.sh 5.34.0
./generate.sh 5.32.0 5.32.1 5.34.0
```

### Requirements

- Git
- Python 3 with `requests` package
- Perl with CPANminus
