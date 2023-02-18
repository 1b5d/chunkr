"""
chunkr can chunk data files and convert them into
other formats (currently parquet) at the same time
"""
from datetime import datetime
import logging
import pathlib
from types import TracebackType
import typing

import fsspec
from pyarrow import csv
import pyarrow as pa
import pyarrow.parquet as pq

from chunkr.exceptions import ChunkrInvalid

logger = logging.getLogger(__file__)


class Chunker:
    """base class to inherit from for a source file type"""

    def __init__(
        self,
        path: str,
        chunk_size: int = 100_000,
        storage_options: typing.Optional[typing.Dict[str, typing.Any]] = None,
        exclude: typing.Optional[typing.List[str]] = None,
    ) -> None:
        """initializes the base class

        Args:
            path (str): the path of the input (local, sftp etc, see fsspec for possible input)
            chunk_size (int, optional): number of records in a chunk. Defaults to 100_000.
            storage_options (dict, optional): options to pass to the underlying storage
                e.g. username, password etc. Defaults to None.
            exclude (list, optional): list of files to be excluded
        """
        self.path: str = path
        self.chunk_size: int = chunk_size
        self.storage_options: typing.Dict[str, typing.Any] = (
            storage_options or {}
        )
        self.exclude: typing.List[str] = exclude or []
        self.selected_files: typing.Dict[str, str] = {}
        self.fs, _ = fsspec.core.url_to_fs(path, **self.storage_options)

    def _get_extension(self) -> str:
        return pathlib.Path(self.path).suffix.lstrip(".")

    def _format_fullname(self, filepath: str) -> str:
        return f"{self.path}->{filepath}"

    def _process_dispatch(self) -> typing.Iterator[pa.RecordBatch]:
        openfiles = fsspec.open_files(
            self.path, compression="infer", **self.storage_options
        )
        self.selected_files = {}
        for openfile in reversed(openfiles):
            fullname = self._format_fullname(openfile.path)
            if fullname in self.exclude:
                logger.debug("excluding file: %s", fullname)
                openfiles.remove(openfile)
                continue
            logger.info("selecting file: %s", fullname)
            self.selected_files[fullname] = datetime.now().isoformat()

        with openfiles as filelikes:
            for filelike in filelikes:
                yield from self._process(filelike)

    def _process(self, filelike: typing.Any) -> typing.Iterator[pa.Table]:
        raise NotImplementedError()

    def __enter__(self) -> typing.Iterator[pa.RecordBatch]:
        try:
            yield from self._process_dispatch()
        except BaseException as exc:
            raise exc

    def __exit__(
        self,
        exc_type: typing.Optional[typing.Type[BaseException]],
        exc_value: typing.Optional[BaseException],
        exc_traceback: typing.Optional[TracebackType],
    ) -> None:
        pass


class CsvChunker(Chunker):
    """a CsvChunker implementation for chunking csv files"""

    def __init__(
        self,
        path: str,
        chunk_size: int = 100_000,
        storage_options: typing.Optional[typing.Dict[str, typing.Any]] = None,
        exclude: typing.Optional[typing.List[str]] = None,
        **kwargs: typing.Dict[str, typing.Any],
    ) -> None:
        self.kwargs = kwargs
        self.chunk_size = chunk_size
        super().__init__(
            path,
            chunk_size,
            storage_options,
            exclude,
        )

    def _estimate_row_size(
        self,
        filelike: typing.Any,
        sample_block_size: typing.Optional[int] = 256 * 1024,
    ) -> int:
        try:
            with csv.open_csv(
                filelike,
                read_options=csv.ReadOptions(block_size=sample_block_size),
                parse_options=csv.ParseOptions(**self.kwargs),
            ) as csv_reader:
                batch = next(iter(csv_reader))
                filelike.seek(0)
                if not batch or batch.num_rows == 0:
                    return 1
                return int(batch.nbytes // batch.num_rows)
        except pa.ArrowInvalid as e:
            raise ChunkrInvalid(str(e)) from e

    def _process(self, filelike: typing.Any) -> typing.Iterator[pa.Table]:
        row_size = self._estimate_row_size(filelike)
        block_size = row_size * self.chunk_size

        try:
            with csv.open_csv(
                filelike,
                read_options=csv.ReadOptions(block_size=block_size),
                parse_options=csv.ParseOptions(**self.kwargs),
            ) as csv_reader:
                batch_capa = 0
                buffered = 0
                while True:
                    try:
                        if buffered == 0:
                            batch = csv_reader.read_next_batch()
                            buffered = batch.num_rows
                        if batch_capa == 0:
                            local_batches = []
                            batch_capa = self.chunk_size

                        to_write = batch.slice(
                            offset=batch.num_rows - buffered,
                            length=min(buffered, batch_capa),
                        )
                        logger.debug("writing %d records", to_write.num_rows)
                        local_batches.append(to_write)

                        batch_capa -= to_write.num_rows
                        buffered -= to_write.num_rows
                        if batch_capa == 0:
                            yield pa.Table.from_batches(local_batches)

                    except StopIteration:
                        if batch_capa > 0:
                            yield pa.Table.from_batches(local_batches)
                        break
        except pa.ArrowInvalid as e:
            raise ChunkrInvalid(str(e)) from e


class ParquetChunker(Chunker):
    """a ParquetChunker implementation for chunking parquet files"""

    def __init__(
        self,
        path: str,
        chunk_size: int = 100_000,
        storage_options: typing.Optional[typing.Dict[str, typing.Any]] = None,
        exclude: typing.Optional[typing.List[str]] = None,
        **kwargs: typing.Dict[str, typing.Any],
    ) -> None:
        self.kwargs = kwargs
        self.chunk_size = chunk_size
        super().__init__(
            path,
            chunk_size,
            storage_options,
            exclude,
        )

    def _process(self, filelike: typing.Any) -> typing.Iterator[pa.Table]:
        parquet_file = pq.ParquetFile(filelike)
        for batch in parquet_file.iter_batches(self.chunk_size, **self.kwargs):
            yield pa.Table.from_batches([batch])


def create_csv_chunk_iter(
    path: str,
    chunk_size: int = 100_000,
    storage_options: typing.Optional[typing.Dict[str, typing.Any]] = None,
    exclude: typing.Optional[typing.List[str]] = None,
    **kwargs: typing.Dict[str, typing.Any],
) -> CsvChunker:
    """creates a new CsvChunker object, which is a context manager that returns an iterator
    over the batches resulted by reading the source file(s)

    Args:
        path (str): the path of the input (local, sftp etc, see fsspec for possible input)
        chunk_size (int, optional): number of records in a chunk. Defaults to 100_000.
        storage_options (typing.Optional[typing.Dict[str, typing.Any]], optional):
         options to pass to the underlying storage e.g. username, password etc.
         Defaults to None.
        exclude (typing.Optional[typing.List[str]], optional): list of files to be excluded.
         Defaults to None.

    Returns:
        CsvChunker: a CsvChunker implementation for chunking csv files
    """
    return CsvChunker(
        path=path,
        chunk_size=chunk_size,
        storage_options=storage_options,
        exclude=exclude,
        **kwargs,
    )


def create_parquet_chunk_iter(
    path: str,
    chunk_size: int = 100_000,
    storage_options: typing.Optional[typing.Dict[str, typing.Any]] = None,
    exclude: typing.Optional[typing.List[str]] = None,
    **kwargs: typing.Dict[str, typing.Any],
) -> ParquetChunker:
    """creates a new ParquetChunker object, which is a context manager that returns an iterator
    over the batches resulted by reading the source file(s)

    Args:
        path (str): the path of the input (local, sftp etc, see fsspec for possible input)
        chunk_size (int, optional): number of records in a chunk. Defaults to 100_000.
        storage_options (typing.Optional[typing.Dict[str, typing.Any]], optional): _description_.
         Defaults to None.
        exclude (typing.Optional[typing.List[str]], optional): _description_. Defaults to None.

    Returns:
        ParquetChunker: _description_
    """
    return ParquetChunker(
        path=path,
        chunk_size=chunk_size,
        storage_options=storage_options,
        exclude=exclude,
        **kwargs,
    )
