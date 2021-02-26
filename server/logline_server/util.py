import asyncio
from functools import partial


try:
    from asyncio import to_thread
except ImportError:
    # asyncio.to_thread is available only in Python 3.9+
    # so for older Python version here is our polyfill:
    async def to_thread(func, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))


async def decompress_zst(compressed_data):
    assert isinstance(compressed_data, bytes)
    try:
        # https://python-zstandard.readthedocs.io/
        import zstandard
        return await to_thread(zstandard.decompress, compressed_data)
    except ImportError:
        pass
    try:
        # https://github.com/sergey-dryabzhinsky/python-zstd
        # https://packages.debian.org/bullseye/python3-zstd
        import zstd
        return await to_thread(zstd.decompress, compressed_data)
    except ImportError:
        pass
    raise Exception('Zstandard decompression is not available - please install zstandard or zstd')
