"""Private, content-addressed artifacts with atomic publication and verified reads.

This filesystem implementation requires durable mounted storage in production;
it does not pretend ephemeral application disks are a backup.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import tempfile
from typing import BinaryIO, Protocol

KEY = re.compile(r'^sha256/([a-f0-9]{2})/([a-f0-9]{64})$')


class ArtifactIntegrityError(ValueError):
    pass


@dataclass(frozen=True)
class StoredArtifact:
    key: str
    sha256: str
    size_bytes: int


class ArtifactStore(Protocol):
    def put(self, stream: BinaryIO, *, max_bytes: int = 256 * 1024 * 1024) -> StoredArtifact: ...
    def open_verified(self, key: str): ...


class LocalArtifactStore:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.staging = self.root/'.staging'
        self.staging.mkdir(exist_ok=True, mode=0o700)

    def _path(self, key):
        match = KEY.fullmatch(key)
        if not match or match[1] != match[2][:2]:
            raise ValueError('Invalid artifact key')
        return self.root/key

    def put(self, stream, *, max_bytes=256 * 1024 * 1024):
        if type(max_bytes) is not int or max_bytes < 0:
            raise ValueError('max_bytes must be a nonnegative integer')
        digest = hashlib.sha256()
        count = 0
        with tempfile.NamedTemporaryFile(dir=self.staging, delete=False) as temp:
            temporary = Path(temp.name)
            try:
                while chunk := stream.read(1024 * 1024):
                    if not isinstance(chunk, bytes):
                        raise TypeError('Artifacts must be binary streams')
                    count += len(chunk)
                    if count > max_bytes:
                        raise ValueError('Artifact exceeds configured size limit')
                    digest.update(chunk)
                    temp.write(chunk)
                temp.flush()
                os.fsync(temp.fileno())
                sha = digest.hexdigest()
                artifact = StoredArtifact(f'sha256/{sha[:2]}/{sha}', sha, count)
                destination = self._path(artifact.key)
                destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                try:
                    os.link(temporary, destination)
                except FileExistsError:
                    with self.open_verified(artifact.key) as existing:
                        if existing.seek(0, 2) != count:
                            raise ArtifactIntegrityError('Existing artifact size mismatch')
                directory_fd = os.open(destination.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
                return artifact
            finally:
                temporary.unlink(missing_ok=True)

    @contextmanager
    def open_verified(self, key):
        path = self._path(key)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as handle:
            digest = hashlib.sha256()
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
            if digest.hexdigest() != path.name:
                raise ArtifactIntegrityError('Artifact checksum mismatch')
            handle.seek(0)
            yield handle
