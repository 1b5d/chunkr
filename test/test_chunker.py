import pytest

from chunkr import create_csv_chunk_iter
from chunkr import create_parquet_chunk_iter
from chunkr.exceptions import ChunkrInvalid


def test_empty():
    with pytest.raises(ChunkrInvalid):
        with create_csv_chunk_iter(
            "test/csv/empty.csv",
            1000,
        ) as chunker:
            for _ in chunker:
                pass


@pytest.mark.parametrize(
    "filepath, chunksize, delimiter, escapechar, quotechar, num_records",
    (
        [
            "test/csv/semicol_dquote_dquote_n_h.csv",
            1000,
            ";",
            "\\",
            '"',
            10000,
        ],
        [
            "test/csv/semicol_dquote_backslash_n_h.csv",
            1000,
            ";",
            "\\",
            '"',
            10000,
        ],
        [
            "test/csv/semicol_dquote_dquote_rn_h.csv",
            1000,
            ";",
            "\\",
            '"',
            10000,
        ],
        [
            "test/csv/semicol_dquote_quote_n_h.csv",
            1000,
            ";",
            "'",
            '"',
            10000,
        ],
        [
            "test/csv/semicol_quote_dquote_n_h.csv",
            1000,
            ";",
            "\\",
            "'",
            10000,
        ],
        [
            "test/csv/comma_dquote_dquote_n_h.csv",
            1000,
            ",",
            "\\",
            '"',
            10000,
        ],
        [
            "test/csv/tab_dquote_dquote_n_h.csv",
            1000,
            "\t",
            "\\",
            '"',
            10000,
        ],
        [
            "test/csv/pipe_dquote_dquote_n_h.csv",
            1000,
            "|",
            "\\",
            '"',
            10000,
        ],
        [
            "test/csv/dir/*.csv",
            1000,
            ";",
            "\\",
            '"',
            20000,
        ],
        [
            "zip://dir/*.csv::test/csv/archive.zip",
            1000,
            ";",
            "\\",
            '"',
            20000,
        ],
        [
            "tar://*.csv::test/csv/archive_single.tar.gz",
            1000,
            ";",
            "\\",
            '"',
            10000,
        ],
    ),
)
def test_csv(
    filepath,
    chunksize,
    delimiter,
    escapechar,
    quotechar,
    num_records,
):
    with create_csv_chunk_iter(
        filepath,
        chunksize,
        quote_char=quotechar,
        delimiter=delimiter,
        escape_char=escapechar,
    ) as chunks_iter:
        num_files = num_records // chunksize
        batches = list(chunks_iter)

        assert num_files == len(batches)

        assert num_records == sum(
            len(batch) for batch in batches
        ), f"total number of records should be [{num_records}]"


@pytest.mark.parametrize(
    "filepath, chunksize, num_files",
    (
        [
            "test/parquet/pyarrow_snappy.parquet",
            1000,
            10,
        ],
        [
            "test/parquet/pyarrow_gzip.parquet",
            1000,
            10,
        ],
        [
            "test/parquet/pyarrow_brotli.parquet",
            1000,
            10,
        ],
        [
            "test/parquet/fastparquet_snappy.parquet",
            1000,
            10,
        ],
        [
            "test/parquet/fastparquet_gzip.parquet",
            1000,
            10,
        ],
        [
            "test/parquet/fastparquet_brotli.parquet",
            1000,
            10,
        ],
        [
            "test/parquet/dir/partition_idx=*/*.parquet",
            1000,
            10,
        ],
        [
            "zip://dir/partition_idx=*/*.parquet::test/parquet/archive.zip",
            1000,
            10,
        ],
        [
            "tar://partition_idx=*/*.parquet::test/parquet/archive.tar.gz",
            1000,
            10,
        ],
    ),
)
def test_parquet(filepath, chunksize, num_files):
    with create_parquet_chunk_iter(filepath, chunksize) as chunks_iter:
        batches = list(chunks_iter)
        assert num_files == len(
            batches
        ), "this file should be split into 10 chunks"
        for batch in batches:
            assert (
                len(batch) == chunksize
            ), f"chunk should contain [{chunksize}] rows"
