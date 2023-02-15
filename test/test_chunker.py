import pandas as pd
import pytest

from chunkr import create_chunks_dir
from chunkr.exceptions import ChunkrInvalid


def test_empty():
    with pytest.raises(ChunkrInvalid):
        with create_chunks_dir(
            "csv",
            "TestTable",
            "test/csv/empty.csv",
            "/tmp",
            1000,
            None,
            None,
        ) as _:
            pass


@pytest.mark.parametrize(
    "fmt, name, temp_dir, filepath, chunksize, delimiter, escapechar, quotechar, num_records",
    (
        [
            "csv",
            "TestTable",
            "/tmp",
            "test/csv/semicol_dquote_dquote_n_h.csv",
            1000,
            ";",
            "\\",
            '"',
            10000,
        ],
        [
            "csv",
            "TestTable",
            "/tmp",
            "test/csv/semicol_dquote_backslash_n_h.csv",
            1000,
            ";",
            "\\",
            '"',
            10000,
        ],
        [
            "csv",
            "TestTable",
            "/tmp",
            "test/csv/semicol_dquote_dquote_rn_h.csv",
            1000,
            ";",
            "\\",
            '"',
            10000,
        ],
        [
            "csv",
            "TestTable",
            "/tmp",
            "test/csv/semicol_dquote_quote_n_h.csv",
            1000,
            ";",
            "'",
            '"',
            10000,
        ],
        [
            "csv",
            "TestTable",
            "/tmp",
            "test/csv/semicol_quote_dquote_n_h.csv",
            1000,
            ";",
            "\\",
            "'",
            10000,
        ],
        [
            "csv",
            "TestTable",
            "/tmp",
            "test/csv/comma_dquote_dquote_n_h.csv",
            1000,
            ",",
            "\\",
            '"',
            10000,
        ],
        [
            "csv",
            "TestTable",
            "/tmp",
            "test/csv/tab_dquote_dquote_n_h.csv",
            1000,
            "\t",
            "\\",
            '"',
            10000,
        ],
        [
            "csv",
            "TestTable",
            "/tmp",
            "test/csv/pipe_dquote_dquote_n_h.csv",
            1000,
            "|",
            "\\",
            '"',
            10000,
        ],
        [
            "csv",
            "TestTable",
            "/tmp",
            "test/csv/dir/*.csv",
            1000,
            ";",
            "\\",
            '"',
            20000,
        ],
        [
            "csv",
            "TestTable",
            "/tmp",
            "zip://dir/*.csv::test/csv/archive.zip",
            1000,
            ";",
            "\\",
            '"',
            20000,
        ],
        [
            "csv",
            "TestTable",
            "/tmp",
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
    fmt,
    name,
    temp_dir,
    filepath,
    chunksize,
    delimiter,
    escapechar,
    quotechar,
    num_records,
):
    with create_chunks_dir(
        fmt,
        name,
        filepath,
        temp_dir,
        chunksize,
        None,
        None,
        quote_char=quotechar,
        delimiter=delimiter,
        escape_char=escapechar,
    ) as chunks_dir:
        num_files = num_records // chunksize

        assert num_files == len(list(chunks_dir.iterdir()))

        assert num_records == sum(
            len(pd.read_parquet(file)) for file in chunks_dir.iterdir()
        ), f"total number of records should be [{num_records}]"
    assert not chunks_dir.exists(), "Chunks Dir should be removed after usage"


@pytest.mark.parametrize(
    "fmt, name, temp_dir, filepath, chunksize, num_files",
    (
        [
            "parquet",
            "TestTable",
            "/tmp",
            "test/parquet/pyarrow_snappy.parquet",
            1000,
            10,
        ],
        [
            "parquet",
            "TestTable",
            "/tmp",
            "test/parquet/pyarrow_gzip.parquet",
            1000,
            10,
        ],
        [
            "parquet",
            "TestTable",
            "/tmp",
            "test/parquet/pyarrow_brotli.parquet",
            1000,
            10,
        ],
        [
            "parquet",
            "TestTable",
            "/tmp",
            "test/parquet/fastparquet_snappy.parquet",
            1000,
            10,
        ],
        [
            "parquet",
            "TestTable",
            "/tmp",
            "test/parquet/fastparquet_gzip.parquet",
            1000,
            10,
        ],
        [
            "parquet",
            "TestTable",
            "/tmp",
            "test/parquet/fastparquet_brotli.parquet",
            1000,
            10,
        ],
        [
            "parquet",
            "TestTable",
            "/tmp",
            "test/parquet/dir/partition_idx=*/*.parquet",
            1000,
            10,
        ],
        [
            "parquet",
            "TestTable",
            "/tmp",
            "zip://dir/partition_idx=*/*.parquet::test/parquet/archive.zip",
            1000,
            10,
        ],
        [
            "parquet",
            "TestTable",
            "/tmp",
            "tar://partition_idx=*/*.parquet::test/parquet/archive.tar.gz",
            1000,
            10,
        ],
    ),
)
def test_parquet(fmt, name, temp_dir, filepath, chunksize, num_files):
    with create_chunks_dir(
        fmt, name, filepath, temp_dir, chunksize
    ) as chunks_dir:
        files = list(chunks_dir.iterdir())
        assert num_files == len(
            files
        ), "this file should be split into 10 chunks"
        for file in files:
            df = pd.read_parquet(file)
            assert (
                len(df) == chunksize
            ), f"chunk file should contain [{chunksize}] in this case"
    assert not chunks_dir.exists(), "Chunks Dir should be removed after usage"


def test_sftp_parquet(sftpserver):
    sftp_path = f"sftp://{sftpserver.host}:{sftpserver.port}/test/parquet/pyarrow_snappy.parquet"

    with open("test/parquet/pyarrow_snappy.parquet", "rb") as f:
        content_structure = {
            "test": {"parquet": {"pyarrow_snappy.parquet": f.read()}}
        }
        with sftpserver.serve_content(content_structure):
            chunks_dir_obj = create_chunks_dir(
                "parquet",
                "TestTable",
                sftp_path,
                "/tmp",
                1000,
                {
                    "username": "user",
                    "password": "pw",
                },
            )
            with chunks_dir_obj as chunks_dir:
                assert 10000 == sum(
                    len(pd.read_parquet(file)) for file in chunks_dir.iterdir()
                ), f"total number of records should be [{10000}]"
            chunks_dir_obj.fs.client.close()
            assert (
                not chunks_dir.exists()
            ), "Chunks Dir should be removed after usage"


def test_selected_files():
    chunks_dir_obj = create_chunks_dir(
        "parquet",
        "TestTable",
        "zip://dir/partition_idx=*/*.parquet::test/parquet/archive.zip",
        "/tmp",
        1000,
    )
    with chunks_dir_obj as _:
        pass
    assert set(chunks_dir_obj.selected_files.keys()) == set(
        [
            "zip://dir/partition_idx=*/*.parquet::test/parquet/archive.zip->dir/partition_idx=1/4c87381207da4a009816ad14f9cd44ed.parquet",
            "zip://dir/partition_idx=*/*.parquet::test/parquet/archive.zip->dir/partition_idx=0/5cdd4f4b6bf24543b6f57309e1b3cf7a.parquet",
        ]
    )


def test_excluded_files():
    chunks_dir_obj = create_chunks_dir(
        "parquet",
        "TestTable",
        "zip://dir/partition_idx=*/*.parquet::test/parquet/archive.zip",
        "/tmp",
        1000,
        exclude=[
            "zip://dir/partition_idx=*/*.parquet::test/parquet/archive.zip->dir/partition_idx=1/4c87381207da4a009816ad14f9cd44ed.parquet"
        ],
    )
    with chunks_dir_obj as _:
        pass
    assert set(chunks_dir_obj.selected_files.keys()) == set(
        [
            "zip://dir/partition_idx=*/*.parquet::test/parquet/archive.zip->dir/partition_idx=0/5cdd4f4b6bf24543b6f57309e1b3cf7a.parquet"
        ]
    )
