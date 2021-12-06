"""A set of custom exceptions."""

__all__ = ["FileExtensionError"]


class FileExtensionError(Exception):
    """An error indicating that the file name has the wrong file extension."""
