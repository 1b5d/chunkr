# chunkr
[![PyPI version][pypi-image]][pypi-url]
<!-- [![Build status][build-image]][build-url] -->
<!-- [![Code coverage][coverage-image]][coverage-url] -->
[![GitHub stars][stars-image]][stars-url]
[![Support Python versions][versions-image]][versions-url]


A library for chunking different types of data files.

## Getting started

```bash
pip install chunkr
```

## Usage

Suppose you want to chunk a csv file of 1 million records into 10 pieces, you can do this

```py
from chunkr import create_chunks_dir
import pandas as pd

with create_chunks_dir(
            'csv',
            'csv_test',
            'path/to/file',
            'temp/output',
            100_000,
            None,
            None,
            quote_char='"',
            delimiter=',',
            escape_char='\\',
    ) as chunks_dir:

        assert 1_000_000 == sum(
            len(pd.read_parquet(file)) for file in chunks_dir.iterdir()
        )

```


<!-- Badges -->

[pypi-image]: https://img.shields.io/pypi/v/chunkr
[pypi-url]: https://pypi.org/project/chunkr/
[build-image]: https://github.com/1b5d/chunkr/actions/workflows/build.yaml/badge.svg
[build-url]: https://github.com/1b5d/chunkr/actions/workflows/build.yaml
[coverage-image]: https://codecov.io/gh/1b5d/chunkr/branch/main/graph/badge.svg
[coverage-url]: https://codecov.io/gh/1b5d/chunkr/
[stars-image]: https://img.shields.io/github/stars/1b5d/chunkr
[stars-url]: https://github.com/1b5d/chunkr
[versions-image]: https://img.shields.io/pypi/pyversions/chunkr
[versions-url]: https://pypi.org/project/chunkr/
