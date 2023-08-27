class IUFIException(Exception):
    """Base of all IUFI Exceptions."""

class ImageLoadError(IUFIException):
    """There was an error while loading the image."""

class DuplicatedCardError(IUFIException):
    """There was a duplicated id in the pool."""

class DuplicatedTagError(IUFIException):
    """There was a duplicated tag in the pool."""