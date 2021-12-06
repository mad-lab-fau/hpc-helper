"""Some utils functions for this package."""
from pathlib import Path
from typing import Optional, Sequence, Union

from hpc_helper._exceptions import FileExtensionError
from hpc_helper._types import path_t


def _assert_file_extension(
    file_name: path_t, expected_extension: Union[str, Sequence[str]], raise_exception: Optional[bool] = True
) -> Optional[bool]:
    """Check if a file has the correct file extension.

    Parameters
    ----------
    file_name : path or str
        file name to check for correct extension
    expected_extension : str or list of str
        file extension (or a list of file extensions) to check for
    raise_exception : bool, optional
        whether to raise an exception or return a bool value

    Returns
    -------
    ``True`` if ``file_name`` ends with one of the specified file extensions, ``False`` otherwise
    (if ``raise_exception`` is ``False``)

    Raises
    ------
    :exc:`~biopsykit.exceptions.FileExtensionError`
        if ``raise_exception`` is ``True`` and ``file_name`` does not end with any of the specified
        ``expected_extension``

    """
    # ensure pathlib
    file_name = Path(file_name)
    if isinstance(expected_extension, str):
        expected_extension = [expected_extension]
    if file_name.suffix not in expected_extension:
        if raise_exception:
            raise FileExtensionError(
                "The file name extension is expected to be one of {}. "
                "Instead it has the following extension: {}".format(expected_extension, file_name.suffix)
            )
        return False
    return True
