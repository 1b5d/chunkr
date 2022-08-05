"""
chunkr can chunk data files and convert them into
other formats (currently parquet) at the same time
"""
import logging
import pathlib
import shutil
import time

import fsspec
from pyarrow import csv
import pyarrow as pa
import pyarrow.parquet as pq

from chunkr.exceptions import ChunkrInvalid

logger = logging.getLogger(__file__)


class ChunksDir:
    """base class to inherit from for a source file type
    """
    file_extensions = None

    def __init__(
        self,
        name,
        path,
        output_path,
        chunk_size=100_000,
        storage_options=None,
        write_options=None,
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
        """
        self.path = path
        self.chunk_size = chunk_size
        self.storage_options = storage_options or {}
        self.write_options = write_options or {}
        self.dir_path = pathlib.Path(
            output_path) / f"chunkr_job_{name}_{time.time()}"
        self.fs, _ = fsspec.core.url_to_fs(path, **self.storage_options)

    def _create_chunk_filename(self):
        file_name = f"chunkr_chunk_{time.time()}.parquet"
        return self.dir_path / file_name

    def _write_chunk(self, df, filename, **write_options):
        logger.debug("writing parquet chunk file %s", filename)
        table = pa.Table.from_pandas(df, **write_options)
        pq.write_table(table, filename, use_deprecated_int96_timestamps=True)

    def _get_extension(self, path):
        return pathlib.Path(path).suffix.lstrip(".")

    def _process_dispatch(self, path):
        openfiles = fsspec.open_files(path,
                                      compression="infer",
                                      **self.storage_options)
        with openfiles as filelikes:
            for filelike in filelikes:
                self._process(filelike)

    def _process(self, path):
        raise NotImplementedError()

    def _cleanup(self):
        logger.debug("cleaning up dir %s", self.dir_path)
        shutil.rmtree(self.dir_path)

    def __enter__(self):
        self.dir_path.mkdir(parents=True, exist_ok=True)
        try:
            self._process_dispatch(self.path)
        except BaseException as exc:
            self._cleanup()
            raise exc

        return self.dir_path

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self._cleanup()


class CsvChunksDir(ChunksDir):
    """a chunksdir implementation for processing csv files
    """
    file_extensions = ["csv"]

    def __init__(
        self,
        name,
        path,
        output_path,
        chunk_size=100_000,
        storage_options=None,
        write_options=None,
        **kwargs,
    ) -> None:
        self.name = name
        self.kwargs = kwargs
        self.chunk_size = chunk_size
        super().__init__(self.name, path, output_path, chunk_size,
                         storage_options, write_options)

    def _estimate_row_size(self, path, sample_block_size=256 * 1024):
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
                return batch.nbytes // batch.num_rows
        except pa.ArrowInvalid as e:
            raise ChunkrInvalid(str(e)) from e

    def _process(self, path):
        row_size = self._estimate_row_size(path)
        block_size = row_size * self.chunk_size

        try:
            with csv.open_csv(
                    path,
                    read_options=csv.ReadOptions(block_size=block_size),
                    parse_options=csv.ParseOptions(
                        **self.kwargs)) as csv_reader:
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
                            pqwriter = pq.ParquetWriter(tmp_file, schema,
                                                        **self.write_options)
                            batch_capa = self.chunk_size

                        to_write = batch.slice(offset=batch.num_rows - buffered,
                                               length=min(buffered, batch_capa))
                        logger.debug('writing %d records', to_write.num_rows)
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
    """a chunksdir implementation for processing parquet files
    """
    file_extensions = ["parquet", "snappy"]

    def __init__(
        self,
        name,
        path,
        output_path,
        chunk_size=100_000,
        storage_options=None,
        write_options=None,
        **kwargs,
    ) -> None:
        self.name = name
        self.kwargs = kwargs
        self.chunk_size = chunk_size
        super().__init__(name, path, output_path, chunk_size, storage_options,
                         write_options)

    def _process(self, path):
        parquet_file = pq.ParquetFile(path)
        for batch in parquet_file.iter_batches(self.chunk_size):
            tmp_file = super()._create_chunk_filename()
            self._write_chunk(batch.to_pandas(), tmp_file, **self.write_options)


formats = {
    "csv": CsvChunksDir,
    "parquet": ParquetChunkDir,
    "snappy": ParquetChunkDir
}


def create_chunks_dir(fmt, *args, **kwargs):
    """creates a ChunksDir object based on input format

    Args:
        fmt (str): input format e.g. csv, parquet ..etc

    Returns:
        ChunksDir: a ChunksDir object implementation suitable for
            the input format
    """
    assert fmt in formats, f"Format [{fmt}] is not supported"
    klass = formats[fmt]

    return klass(*args, **kwargs)
