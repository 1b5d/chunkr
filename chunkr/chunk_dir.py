"""
chunkr can chunk data files and convert them into
other formats (currently parquet) at the same time
"""
import logging
import pathlib
import shutil
import time
from types import TracebackType
import typing

from fsspec import AbstractFileSystem
import pyarrow as pa
import pyarrow.parquet as pq

from chunkr.chunker import Chunker
from chunkr.chunker import CsvChunker
from chunkr.chunker import ParquetChunker

logger = logging.getLogger(__file__)


class ChunkDir:
    """base class to inherit from for a source file type"""

    def __init__(
        self,
        chunker: Chunker,
        output_path: str,
        write_options: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ) -> None:
        """initializes the base class

        Args:
            chunker (Chunker): a file type chunker implementation instance
            output_path (str): the path of the directory to output the chunks to
            write_options (dict, optional): options for writing the chunks passed to the
                respective library. Defaults to None.
        """
        self.chunker = chunker
        self.write_options: typing.Dict[str, typing.Any] = write_options or {}
        self._dir_path = pathlib.Path(output_path) / f"chunkr_job_{time.time()}"

    def _create_chunk_filename(self) -> pathlib.Path:
        file_name = f"chunkr_chunk_{time.time()}.parquet"
        return self._dir_path / file_name

    def _cleanup(self) -> None:
        logger.debug("cleaning up dir %s", self._dir_path)
        shutil.rmtree(self._dir_path)

    def _write_chunk(self, table: pa.Table, filename: pathlib.Path) -> None:
        logger.debug("writing parquet chunk file %s", filename)
        pq.write_table(table, filename, **self.write_options)

    def _write_chunks(self) -> None:
        with self.chunker as chunk_iter:
            for chunk in chunk_iter:
                tmp_file = self._create_chunk_filename()
                self._write_chunk(chunk, tmp_file, **self.write_options)

    def __enter__(self) -> pathlib.Path:
        self._dir_path.mkdir(parents=True, exist_ok=True)
        try:
            self._write_chunks()
        except BaseException as exc:
            self._cleanup()
            raise exc

        return self._dir_path

    def __exit__(
        self,
        exc_type: typing.Optional[typing.Type[BaseException]],
        exc_value: typing.Optional[BaseException],
        exc_traceback: typing.Optional[TracebackType],
    ) -> None:
        self._cleanup()

    @property
    def fs(self) -> AbstractFileSystem:
        """returns the fs object which was created in related to the input files

        Returns:
            fsspec.FileSystem: _description_
        """
        return self.chunker.fs

    @property
    def selected_files(self) -> typing.Dict[str, str]:
        """maps the concrete file names which were selected for chunking
         with the datetime in which the process started (time of opening the file)

        Returns:
            typing.Dict[str, str]: a dict mapping file names to datetimes
        """
        return self.chunker.selected_files


class CsvChunkDir(ChunkDir):
    """a chunksdir implementation for processing csv files"""

    def __init__(
        self,
        path: str,
        output_path: str,
        chunk_size: int = 100_000,
        storage_options: typing.Optional[typing.Dict[str, typing.Any]] = None,
        write_options: typing.Optional[typing.Dict[str, typing.Any]] = None,
        exclude: typing.Optional[typing.List[str]] = None,
        **kwargs: typing.Dict[str, typing.Any],
    ) -> None:
        super().__init__(
            CsvChunker(
                path,
                chunk_size=chunk_size,
                storage_options=storage_options,
                exclude=exclude,
                **kwargs,
            ),
            output_path=output_path,
            write_options=write_options,
        )


class ParquetChunkDir(ChunkDir):
    """a chunksdir implementation for processing parquet files"""

    def __init__(
        self,
        path: str,
        output_path: str,
        chunk_size: int = 100_000,
        storage_options: typing.Optional[typing.Dict[str, typing.Any]] = None,
        write_options: typing.Optional[typing.Dict[str, typing.Any]] = None,
        exclude: typing.Optional[typing.List[str]] = None,
        **kwargs: typing.Dict[str, typing.Any],
    ) -> None:
        super().__init__(
            ParquetChunker(
                path,
                chunk_size=chunk_size,
                storage_options=storage_options,
                exclude=exclude,
                **kwargs,
            ),
            output_path=output_path,
            write_options=write_options,
        )


formats = {
    "csv": CsvChunkDir,
    "parquet": ParquetChunkDir,
    "snappy": ParquetChunkDir,
}


def create_chunks_dir(
    fmt: str,
    *args: typing.Any,
    **kwargs: typing.Any,
) -> ChunkDir:
    """creates a ChunksDir object based on input format
    method is deprecated, please use create_chunks_csv_dir,
        create_chunks_parquet_dir ..etc.

    Args:
        fmt (str): input format e.g. csv, parquet ..etc

    Returns:
        ChunksDir: a ChunksDir object implementation suitable for
            the input format
    """
    assert fmt in formats, f"Format [{fmt}] is not supported"
    klass = formats[fmt]

    # remove the first argument to stay backward compatible (with v0.2.1)

    return klass(*args[1:], **kwargs)


def create_csv_chunk_dir(
    path: str,
    output_path: str,
    chunk_size: int = 100_000,
    storage_options: typing.Optional[typing.Dict[str, typing.Any]] = None,
    write_options: typing.Optional[typing.Dict[str, typing.Any]] = None,
    exclude: typing.Optional[typing.List[str]] = None,
    **kwargs: typing.Dict[str, typing.Any],
) -> CsvChunkDir:
    """creates a ChunksDir for a csv input path, or a directory

    Args:
        path (str): the path of the input (local, sftp etc, see fsspec for possible input)
        output_path (str): the path of the directory to output the chunks to
        chunk_size (int, optional): number of records in a chunk. Defaults to 100_000.
        storage_options (dict, optional): options to pass to the underlying storage
            e.g. username, password etc. Defaults to None.
        write_options (dict, optional): options for writing the chunks passed to the
            respective library. Defaults to None.
        exclude (list, optional): list of files to be excluded. Defaults to None.

    Returns:
        CsvChunksDir: a CsvChunksDir object
    """
    return CsvChunkDir(
        path=path,
        output_path=output_path,
        chunk_size=chunk_size,
        storage_options=storage_options,
        write_options=write_options,
        exclude=exclude,
        **kwargs,
    )


def create_parquet_chunk_dir(
    path: str,
    output_path: str,
    chunk_size: int = 100_000,
    storage_options: typing.Optional[typing.Dict[str, typing.Any]] = None,
    write_options: typing.Optional[typing.Dict[str, typing.Any]] = None,
    exclude: typing.Optional[typing.List[str]] = None,
    **kwargs: typing.Dict[str, typing.Any],
) -> ParquetChunkDir:
    """creates a ChunksDir for a parquet input path, or a directory

    Args:
        path (str): the path of the input (local, sftp etc, see fsspec for possible input)
        output_path (str): the path of the directory to output the chunks to
        chunk_size (int, optional): number of records in a chunk. Defaults to 100_000.
        storage_options (dict, optional): options to pass to the underlying storage
            e.g. username, password etc. Defaults to None.
        write_options (dict, optional): options for writing the chunks passed to the
            respective library. Defaults to None.
        exclude (list, optional): list of files to be excluded. Defaults to None.

    Returns:
        ParquetChunkDir: a ParquetChunkDir object
    """

    return ParquetChunkDir(
        path=path,
        output_path=output_path,
        chunk_size=chunk_size,
        storage_options=storage_options,
        write_options=write_options,
        exclude=exclude,
        **kwargs,
    )
