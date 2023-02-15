"""
chunkr can chunk data files and convert them into
other formats (currently parquet) at the same time
"""
from datetime import datetime
import logging
import pathlib
import shutil
import time
from types import TracebackType
import typing

import fsspec
import pandas as pd
from pyarrow import csv
import pyarrow as pa
import pyarrow.parquet as pq

from chunkr.exceptions import ChunkrInvalid

logger = logging.getLogger(__file__)


class ChunksDir:
    """base class to inherit from for a source file type"""

    def __init__(
        self,
        name: str,
        path: str,
        output_path: str,
        chunk_size: int = 100_000,
        storage_options: typing.Optional[typing.Dict[str, typing.Any]] = None,
        write_options: typing.Optional[typing.Dict[str, typing.Any]] = None,
        exclude: typing.Optional[typing.List[str]] = None,
    ) -> None:
        """initializes the base class

        Args:
            name (str): a distinct name of the chunking job
            path (str): the path of the input (local, sftp etc, see fsspec for possible input)
            output_path (str): the path of the directory to output the chunks to
            chunk_size (int, optional): number of records in a chunk. Defaults to 100_000.
            storage_options (dict, optional): options to pass to the underlying storage
                e.g. username, password etc. Defaults to None.
            write_options (dict, optional): options for writing the chunks passed to the
                respective library. Defaults to None.
            exclude (list, optional): list of files to be excluded
        """
        self.path: str = path
        self.chunk_size: int = chunk_size
        self.storage_options: typing.Dict[str, typing.Any] = (
            storage_options or {}
        )
        self.write_options: typing.Dict[str, typing.Any] = write_options or {}
        self.exclude: typing.List[str] = exclude or []
        self.selected_files: typing.Dict[str, str] = {}
        self._dir_path = (
            pathlib.Path(output_path) / f"chunkr_job_{name}_{time.time()}"
        )
        self.fs, _ = fsspec.core.url_to_fs(path, **self.storage_options)

    def _create_chunk_filename(self) -> pathlib.Path:
        file_name = f"chunkr_chunk_{time.time()}.parquet"
        return self._dir_path / file_name

    def _write_chunk(
        self,
        df: pd.DataFrame,
        filename: pathlib.Path,
        **write_options: typing.Dict[str, typing.Any],
    ) -> None:
        logger.debug("writing parquet chunk file %s", filename)
        table = pa.Table.from_pandas(df, **write_options)
        pq.write_table(table, filename, use_deprecated_int96_timestamps=True)

    def _get_extension(self) -> str:
        return pathlib.Path(self.path).suffix.lstrip(".")

    def _format_fullname(self, filepath: str) -> str:
        return f"{self.path}->{filepath}"

    def _process_dispatch(self) -> None:
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
                self._process(filelike)

    def _process(self, path: typing.Any) -> None:
        raise NotImplementedError()

    def _cleanup(self) -> None:
        logger.debug("cleaning up dir %s", self._dir_path)
        shutil.rmtree(self._dir_path)

    def __enter__(self) -> pathlib.Path:
        self._dir_path.mkdir(parents=True, exist_ok=True)
        try:
            self._process_dispatch()
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


class CsvChunksDir(ChunksDir):
    """a chunksdir implementation for processing csv files"""

    def __init__(
        self,
        name: str,
        path: str,
        output_path: str,
        chunk_size: int = 100_000,
        storage_options: typing.Optional[typing.Dict[str, typing.Any]] = None,
        write_options: typing.Optional[typing.Dict[str, typing.Any]] = None,
        exclude: typing.Optional[typing.List[str]] = None,
        **kwargs: typing.Dict[str, typing.Any],
    ) -> None:
        self.name = name
        self.kwargs = kwargs
        self.chunk_size = chunk_size
        super().__init__(
            self.name,
            path,
            output_path,
            chunk_size,
            storage_options,
            write_options,
            exclude,
        )

    def _estimate_row_size(
        self,
        path: typing.Any,
        sample_block_size: typing.Optional[int] = 256 * 1024,
    ) -> int:
        try:
            with csv.open_csv(
                path,
                read_options=csv.ReadOptions(block_size=sample_block_size),
                parse_options=csv.ParseOptions(**self.kwargs),
            ) as csv_reader:
                batch = next(iter(csv_reader))
                path.seek(0)
                if not batch or batch.num_rows == 0:
                    return 1
                return int(batch.nbytes // batch.num_rows)
        except pa.ArrowInvalid as e:
            raise ChunkrInvalid(str(e)) from e

    def _process(self, path: typing.Any) -> None:
        row_size = self._estimate_row_size(path)
        block_size = row_size * self.chunk_size

        try:
            with csv.open_csv(
                path,
                read_options=csv.ReadOptions(block_size=block_size),
                parse_options=csv.ParseOptions(**self.kwargs),
            ) as csv_reader:
                batch_capa = 0
                buffered = 0
                while True:
                    try:
                        if buffered == 0:
                            batch = csv_reader.read_next_batch()
                            schema = batch.schema
                            buffered = batch.num_rows
                        if batch_capa == 0:
                            tmp_file = super()._create_chunk_filename()
                            pqwriter = pq.ParquetWriter(
                                tmp_file, schema, **self.write_options
                            )
                            batch_capa = self.chunk_size

                        to_write = batch.slice(
                            offset=batch.num_rows - buffered,
                            length=min(buffered, batch_capa),
                        )
                        logger.debug("writing %d records", to_write.num_rows)
                        pqwriter.write_batch(to_write)
                        batch_capa -= to_write.num_rows
                        buffered -= to_write.num_rows
                        if batch_capa == 0:
                            pqwriter.close()
                    except StopIteration:
                        pqwriter.close()
                        break
        except pa.ArrowInvalid as e:
            raise ChunkrInvalid(str(e)) from e


class ParquetChunkDir(ChunksDir):
    """a chunksdir implementation for processing parquet files"""

    def __init__(
        self,
        name: str,
        path: str,
        output_path: str,
        chunk_size: int = 100_000,
        storage_options: typing.Optional[typing.Dict[str, typing.Any]] = None,
        write_options: typing.Optional[typing.Dict[str, typing.Any]] = None,
        exclude: typing.Optional[typing.List[str]] = None,
        **kwargs: typing.Dict[str, typing.Any],
    ) -> None:
        self.name = name
        self.kwargs = kwargs
        self.chunk_size = chunk_size
        super().__init__(
            name,
            path,
            output_path,
            chunk_size,
            storage_options,
            write_options,
            exclude,
        )

    def _process(self, path: typing.Any) -> None:
        parquet_file = pq.ParquetFile(path)
        for batch in parquet_file.iter_batches(self.chunk_size):
            tmp_file = super()._create_chunk_filename()
            self._write_chunk(batch.to_pandas(), tmp_file, **self.write_options)


formats = {
    "csv": CsvChunksDir,
    "parquet": ParquetChunkDir,
    "snappy": ParquetChunkDir,
}


def create_chunks_dir(
    fmt: str,
    *args: typing.Any,
    **kwargs: typing.Any,
) -> ChunksDir:
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

    return klass(*args, **kwargs)


def create_chunks_dir_csv(
    path: str,
    output_path: str,
    chunk_size: int = 100_000,
    storage_options: typing.Optional[typing.Dict[str, typing.Any]] = None,
    write_options: typing.Optional[typing.Dict[str, typing.Any]] = None,
    exclude: typing.Optional[typing.List[str]] = None,
    **kwargs: typing.Dict[str, typing.Any],
) -> CsvChunksDir:
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
    return CsvChunksDir(
        "chunkr_temp_dir",
        path=path,
        output_path=output_path,
        chunk_size=chunk_size,
        storage_options=storage_options,
        write_options=write_options,
        exclude=exclude,
        **kwargs,
    )


def create_chunks_parquet_csv(
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
        "chunkr_temp_dir",
        path=path,
        output_path=output_path,
        chunk_size=chunk_size,
        storage_options=storage_options,
        write_options=write_options,
        exclude=exclude,
        **kwargs,
    )
