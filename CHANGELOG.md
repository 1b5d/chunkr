
<a id='changelog-0.3.0'></a>
# 0.3.0 — 2023-02-18

## Added

- added the ability to loop with iterators over resulting batches
- added create_csv_chunk_iter, create_csv_chunk_dir, create_parquet_chunk_iter, create_parquet_chunk_dir endpoints
- add type hints

## Changed

- clean up python envs and deps

## Deprecated

- create_chunks_dir is now deprecated, but can still be used until the next major version

<a id='changelog-0.2.1'></a>
# 0.2.1 — 2023-01-23

## Removed

- Support for Python < 3.8

## Changed

- Security updates through the upgrade of dependecies

<a id='changelog-0.2.0'></a>
# 0.2.0 — 2022-08-22

## Added

- Processsed files through `chunks_dir.selected_files`
- Exclude specific files e.g. `create_chunks_dir(..., exclude=['filename..'])`

<a id='changelog-0.1.3'></a>
# 0.1.3 — 2022-08-05

## Added

- More documentation
- Corner test case

## Fixed

- Chunking CSV into equal chunks

<a id='changelog-0.1.0'></a>
# 0.1.0 — 2022-08-02

## Added

- Initial version
