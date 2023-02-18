# chunkr
[![PyPI version][pypi-image]][pypi-url]
<!-- [![Build status][build-image]][build-url] -->
<!-- [![Code coverage][coverage-image]][coverage-url] -->
<!-- [![GitHub stars][stars-image]][stars-url] -->
[![Support Python versions][versions-image]][versions-url]


A python library for the purpose of chunking different types of data files, without having to store the whole file in memory.

chunkr creates chunks from the source file with a user defined chunk size, then returns an iterator to loop over the resulting batches sequentially.

The type of a resulting batch is PyArrow's [Table](https://arrow.apache.org/docs/python/generated/pyarrow.Table.html#pyarrow-table) due to PyArrow's [performance](https://towardsdatascience.com/stop-using-pandas-to-read-write-data-this-alternative-is-7-times-faster-893301633475) in reading & writing data files.

It's also possible to create a directory which contains the chunks as parquet files (currently only parquet is possible, new suggestions are welcomed), which will be cleaned up automatically when the user is done with the resulting files.

Currently supported input formats: csv, parquet

# Getting started

```bash
pip install chunkr
```

# Usage

## Iterate over resulting batches

CSV input:

```py
from chunkr import create_csv_chunk_iter

with create_csv_chunk_iter(path, chunk_size, storage_options, **extra_args) as chunk_iter:
    # process chunks
    for chunk in chunk_iter:
        # process chunk.to_pandas() or sth

```

Parquet:

```py
from chunkr import create_parquet_chunk_iter

with create_parquet_chunk_iter(path, chunk_size, storage_options, **extra_args) as chunk_iter:
    # process chunks
    for chunk in chunk_iter:
        # process chunk.to_pandas() or sth

```

parameters:

- path (str): the path of the input (local, sftp etc, see [fsspec](https://filesystem-spec.readthedocs.io/en/latest/) for possible inputs, not everything is supported though)
- chunk_size (int, optional): number of records in a chunk. Defaults to 100_000.
- storage_options (dict, optional): extra options to pass to the underlying storage e.g. username, password etc. Defaults to None.
- extra_args (dict, optional): extra options passed on to the parsing system, file type specific


## Create a directory containing the chunks as Parquet files

CSV input:

```py
from chunkr import create_csv_chunk_dir

with create_csv_chunk_dir(input_filepath, output_dir, chunk_size, storage_options, write_options, exclude, **extra_args) as chunks_dir:
    # process chunk files inside dir
    pd.read_parquet(file) for file in chunks_dir.iterdir()
    # the directory will be deleted when the context manager exits 
```

or Parquet:

```py
from chunkr import create_csv_chunk_dir

with create_csv_chunk_dir(input_filepath, output_dir, chunk_size, storage_options, write_options, exclude, **extra_args) as chunks_dir:
    # process chunk files inside dir
    pd.read_parquet(file) for file in chunks_dir.iterdir()
    # the directory will be deleted when the context manager exits
```


parameters:

- path (str): the path of the input (local, sftp etc, see fsspec for possible input)
- output_path (str): the path of the directory to output the chunks to
- chunk_size (int, optional): number of records in a chunk. Defaults to 100_000.
- storage_options (dict, optional): extra options to pass to the underlying storage e.g. username, password etc. Defaults to None.
- write_options (dict, optional): extra options for writing the chunks passed to PyArrow's [write_table()](https://arrow.apache.org/docs/python/generated/pyarrow.parquet.write_table.html) function. Defaults to None.
- extra_args (dict, optional): extra options passed on to the parsing system, file specific

>**Note**: currently chunkr only supports parquet as the output chunk files format

# Additional examples


## CSV input

Suppose you want to chunk a csv file of 1 million records into 10 parquet pieces, you can do the following:

CSV extra args are passed to PyArrows [Parsing Options](https://arrow.apache.org/docs/python/generated/pyarrow.csv.ParseOptions.html#pyarrow.csv.ParseOptions)

```py
from chunkr import create_csv_chunk_dir
import pandas as pd

with create_csv_chunk_dir(
            'path/to/file',
            'temp/output',
            chunk_size=100_000,
            quote_char='"',
            delimiter=',',
            escape_char='\\',
    ) as chunks_dir:

        assert 1_000_000 == sum(
            len(pd.read_parquet(file)) for file in chunks_dir.iterdir()
        )
```

## Parquet input

Parquet extra args are passed to PyArrows [iter_batches()](https://arrow.apache.org/docs/python/generated/pyarrow.parquet.ParquetFile.html#pyarrow.parquet.ParquetFile.iter_batches) function

```py
from chunkr import create_parquet_chunk_dir
import pandas as pd

with create_parquet_chunk_dir(
            'path/to/file',
            'temp/output',
            chunk_size=100_000,
            columns=['id', 'name'],
    ) as chunks_dir:

        assert 1_000_000 == sum(
            len(pd.read_parquet(file)) for file in chunks_dir.iterdir()
        )
```

## Reading file(s) inside an archive (zip, tar)

reading multiple files from a zip archive is possible, for csv files in `/folder_in_archive/*.csv` within an archive `csv/archive.zip` you can do:

```py
from chunkr import create_csv_chunk_iter
import pandas as pd

path = 'zip://folder_in_archive/*.csv::csv/archive.zip'
with create_csv_chunk_iter(path) as chunk_iter:
    assert 1_000_000 == sum(len(chunk) for chunk in chunk_iter)
```

The only exception is when particularly reading a csv file from a tar.gz, there can be **only 1 csv file** within the archive:

```py
from chunkr import create_csv_chunk_iter
import pandas as pd

path = 'tar://*.csv::csv/archive_single.tar.gz'
with create_csv_chunk_iter(path) as chunk_iter:
    assert 1_000_000 == sum(len(chunk) for chunk in chunk_iter)
```

but it's okay for other file types like parquet:

```py
from chunkr import create_parquet_chunk_iter
import pandas as pd

path = 'tar://partition_idx=*/*.parquet::test/parquet/archive.tar.gz'
with create_parquet_chunk_iter(path) as chunk_iter:
    assert 1_000_000 == sum(len(chunk) for chunk in chunk_iter)
```

## Reading from an SFTP remote system

To authenticate to the SFTP server, you can pass the credentials via storage_options:

```py
from chunkr import create_parquet_chunk_iter
import pandas as pd

sftp_path = f"sftp://{sftpserver.host}:{sftpserver.port}/parquet/pyarrow_snappy.parquet"

with create_parquet_chunk_iter(
        sftp_path,
        storage_options={
            "username": "user",
            "password": "pw",
        }
    ) as chunk_iter:
    assert 1_000_000 == sum(len(chunk) for chunk in chunk_iter)
```

Reading from a URL

```py
from chunkr import create_parquet_chunk_iter
import pandas as pd

url = "https://example.com/1mil.parquet"

with create_parquet_chunk_iter(url) as chunk_iter:
    assert 1_000_000 == sum(len(chunk) for chunk in chunk_iter)
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
