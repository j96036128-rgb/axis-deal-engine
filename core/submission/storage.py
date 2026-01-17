"""
Document Storage - Secure File Storage for Agent Submissions

Handles secure storage and retrieval of uploaded documents.
Documents are stored with integrity verification (SHA-256 hash).
"""

from __future__ import annotations

import hashlib
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Final, Optional, BinaryIO

from core.submission.schema import (
    DocumentType,
    DocumentRecord,
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE_BYTES,
)


# =============================================================================
# Storage Configuration
# =============================================================================

DEFAULT_STORAGE_PATH: Final[str] = "data/documents"


# =============================================================================
# Document Storage
# =============================================================================


class DocumentStorage:
    """
    Secure document storage for agent submissions.

    Documents are stored in a structured directory hierarchy:
    {storage_root}/{property_id}/{document_type}/{filename}

    Each document is verified with SHA-256 hash for integrity.
    """

    def __init__(self, storage_root: Optional[str] = None):
        """
        Initialise document storage.

        Args:
            storage_root: Root directory for document storage.
                         Defaults to data/documents.
        """
        self._storage_root = Path(storage_root or DEFAULT_STORAGE_PATH)
        self._ensure_storage_exists()

    def _ensure_storage_exists(self) -> None:
        """Ensure storage directory exists."""
        self._storage_root.mkdir(parents=True, exist_ok=True)

    @property
    def storage_root(self) -> Path:
        """Get storage root path."""
        return self._storage_root

    def _get_property_path(self, property_id: str) -> Path:
        """Get storage path for a property."""
        return self._storage_root / property_id

    def _get_document_path(
        self,
        property_id: str,
        document_type: DocumentType,
        filename: str,
    ) -> Path:
        """Get full storage path for a document."""
        # Sanitise filename
        safe_filename = self._sanitise_filename(filename)
        return self._get_property_path(property_id) / document_type.value / safe_filename

    @staticmethod
    def _sanitise_filename(filename: str) -> str:
        """Sanitise filename for safe storage."""
        # Remove path separators and other dangerous characters
        safe = filename.replace("/", "_").replace("\\", "_").replace("..", "_")
        # Remove leading/trailing whitespace and dots
        safe = safe.strip().strip(".")
        # Ensure not empty
        if not safe:
            safe = "document"
        return safe

    @staticmethod
    def _calculate_hash(file_content: bytes) -> str:
        """Calculate SHA-256 hash of file content."""
        return hashlib.sha256(file_content).hexdigest()

    def validate_file(
        self,
        filename: str,
        file_size: int,
    ) -> tuple[bool, Optional[str]]:
        """
        Validate file before upload.

        Args:
            filename: Original filename
            file_size: File size in bytes

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check extension
        ext = ""
        if "." in filename:
            ext = "." + filename.rsplit(".", 1)[-1].lower()

        if ext not in ALLOWED_EXTENSIONS:
            return False, f"Invalid file extension: {ext}. Allowed: {ALLOWED_EXTENSIONS}"

        # Check size
        if file_size > MAX_FILE_SIZE_BYTES:
            max_mb = MAX_FILE_SIZE_BYTES / (1024 * 1024)
            return False, f"File too large. Maximum size: {max_mb}MB"

        if file_size == 0:
            return False, "File is empty"

        return True, None

    def store_document(
        self,
        property_id: str,
        document_type: DocumentType,
        filename: str,
        content: bytes,
    ) -> DocumentRecord:
        """
        Store a document and return its record.

        Args:
            property_id: Property ID this document belongs to
            document_type: Type of document
            filename: Original filename
            content: File content as bytes

        Returns:
            DocumentRecord with storage metadata

        Raises:
            ValueError: If file validation fails
        """
        # Validate file
        is_valid, error = self.validate_file(filename, len(content))
        if not is_valid:
            raise ValueError(error)

        # Calculate hash for integrity
        content_hash = self._calculate_hash(content)

        # Determine storage path
        storage_path = self._get_document_path(property_id, document_type, filename)

        # Ensure directory exists
        storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        storage_path.write_bytes(content)

        # Create and return record
        return DocumentRecord.create(
            document_type=document_type,
            filename=filename,
            file_size_bytes=len(content),
            content_hash=content_hash,
            storage_path=str(storage_path),
        )

    def store_document_from_file(
        self,
        property_id: str,
        document_type: DocumentType,
        filename: str,
        file_handle: BinaryIO,
    ) -> DocumentRecord:
        """
        Store a document from a file handle.

        Args:
            property_id: Property ID this document belongs to
            document_type: Type of document
            filename: Original filename
            file_handle: File-like object to read from

        Returns:
            DocumentRecord with storage metadata
        """
        content = file_handle.read()
        return self.store_document(property_id, document_type, filename, content)

    def retrieve_document(self, storage_path: str) -> Optional[bytes]:
        """
        Retrieve document content by storage path.

        Args:
            storage_path: Path from DocumentRecord.storage_path

        Returns:
            File content as bytes, or None if not found
        """
        path = Path(storage_path)
        if path.exists():
            return path.read_bytes()
        return None

    def verify_document(self, record: DocumentRecord) -> bool:
        """
        Verify document integrity using stored hash.

        Args:
            record: DocumentRecord to verify

        Returns:
            True if document matches stored hash, False otherwise
        """
        content = self.retrieve_document(record.storage_path)
        if content is None:
            return False

        current_hash = self._calculate_hash(content)
        return current_hash == record.content_hash

    def delete_document(self, storage_path: str) -> bool:
        """
        Delete a document from storage.

        Args:
            storage_path: Path from DocumentRecord.storage_path

        Returns:
            True if deleted, False if not found
        """
        path = Path(storage_path)
        if path.exists():
            path.unlink()
            return True
        return False

    def delete_property_documents(self, property_id: str) -> int:
        """
        Delete all documents for a property.

        Args:
            property_id: Property ID

        Returns:
            Number of files deleted
        """
        property_path = self._get_property_path(property_id)
        if not property_path.exists():
            return 0

        count = 0
        for file_path in property_path.rglob("*"):
            if file_path.is_file():
                file_path.unlink()
                count += 1

        # Remove empty directories
        shutil.rmtree(property_path, ignore_errors=True)
        return count

    def get_property_documents(self, property_id: str) -> list[Path]:
        """
        List all documents for a property.

        Args:
            property_id: Property ID

        Returns:
            List of file paths
        """
        property_path = self._get_property_path(property_id)
        if not property_path.exists():
            return []

        return [p for p in property_path.rglob("*") if p.is_file()]

    def get_storage_stats(self) -> dict:
        """
        Get storage statistics.

        Returns:
            Dict with total_files, total_size_bytes, properties_count
        """
        total_files = 0
        total_size = 0
        properties = set()

        for file_path in self._storage_root.rglob("*"):
            if file_path.is_file():
                total_files += 1
                total_size += file_path.stat().st_size
                # Property ID is first directory under root
                relative = file_path.relative_to(self._storage_root)
                if relative.parts:
                    properties.add(relative.parts[0])

        return {
            "total_files": total_files,
            "total_size_bytes": total_size,
            "properties_count": len(properties),
        }


# =============================================================================
# Singleton Instance
# =============================================================================

_storage_instance: Optional[DocumentStorage] = None


def get_document_storage(storage_root: Optional[str] = None) -> DocumentStorage:
    """
    Get the document storage singleton.

    Args:
        storage_root: Optional custom storage root (only used on first call)

    Returns:
        DocumentStorage instance
    """
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = DocumentStorage(storage_root)
    return _storage_instance
