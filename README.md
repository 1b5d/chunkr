# chunkr
[![PyPI version][pypi-image]][pypi-url]
<!-- [![Build status][build-image]][build-url] -->
<!-- [![Code coverage][coverage-image]][coverage-url] -->
<!-- [![GitHub stars][stars-image]][stars-url] -->
[![Support Python versions][versions-image]][versions-url]


A library for chunking different types of data files into another file format. Large files friendly.

Currently supported input formats: csv, parquet

## Getting started

```bash
pip install chunkr
```

## Usage

```py
from chunkr import create_chunks_dir

with create_chunks_dir(file_format, name, input_filepath, output_dir, chunk_size, **extra_args) as chunks_dir:
    # process chunk files inside dir
```

parameters:

- format (str): input format (csv, parquet)
- name (str): a distinct name of the chunking job
- path (str): the path of the input (local, sftp etc, see fsspec for possible input)
- output_path (str): the path of the directory to output the chunks to
- chunk_size (int, optional): number of records in a chunk. Defaults to 100_000.
- storage_options (dict, optional): extra options to pass to the underlying storage e.g. username, password etc. Defaults to None.
- write_options (dict, optional): extra options for writing the chunks passed to the respective library. Defaults to None.
- extra_args (dict, optional): extra options passed on to the parsing system, file specific

>**Note**: currently chunkr only supports parquet as the output chunk files format

## Examples


### CSV

Suppose you want to chunk a csv file of 1 million records into 10 parquet pieces, you can do this

CSV extra args are passed to PyArrows [Parsing Options](https://arrow.apache.org/docs/python/generated/pyarrow.csv.ParseOptions.html#pyarrow.csv.ParseOptions)

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

### Parquet

```py
from chunkr import create_chunks_dir
import pandas as pd

with create_chunks_dir(
            'parquet',
            'parquet_test',
            'path/to/file',
            'temp/output'
    ) as chunks_dir:

        assert 1_000_000 == sum(
            len(pd.read_parquet(file)) for file in chunks_dir.iterdir()
        )
```


### Reading file(s) inside an archive (zip, tar)


reading multiple files from a zip archive is possible, for csv files in `/folder_in_archive/*.csv` within an archive `csv/archive.zip` you can do:

```py
from chunkr import create_chunks_dir
import pandas as pd

with create_chunks_dir(
            'csv',
            'csv_test_zip',
            'zip://folder_in_archive/*.csv::csv/archive.zip',
            'temp/output'
    ) as chunks_dir:

        assert 1_000_000 == sum(
            len(pd.read_parquet(file)) for file in chunks_dir.iterdir()
        )
```

The only exception is when particularly reading a csv file from a tar.gz, there can be **only 1 csv file** within the archive:

```py
from chunkr import create_chunks_dir
import pandas as pd

with create_chunks_dir(
            'csv',
            'csv_test_tar',
            'tar://*.csv::csv/archive_single.tar.gz',
            'temp/output'
    ) as chunks_dir:

        assert 1_000_000 == sum(
            len(pd.read_parquet(file)) for file in chunks_dir.iterdir()
        )
```

but it's okay for other file types like parquet:


```py
from chunkr import create_chunks_dir
import pandas as pd

with create_chunks_dir(
            'parquet',
            'parquet_test',
            'tar://partition_idx=*/*.parquet::test/parquet/archive.tar.gz',
            'temp/output'
    ) as chunks_dir:

        assert 1_000_000 == sum(
            len(pd.read_parquet(file)) for file in chunks_dir.iterdir()
        )
```

### Reading from an SFTP remote system

To authenticate to the SFTP server, you can pass the credentials via storage_options:

```py
from chunkr import create_chunks_dir
import pandas as pd

sftp_path = f"sftp://{sftpserver.host}:{sftpserver.port}/parquet/pyarrow_snappy.parquet"

with create_chunks_dir(
            'parquet',
            'parquet_test_sftp',
            sftp_path,
            'temp/output',
            1000,
            {
                "username": "user",
                "password": "pw",
            }
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
