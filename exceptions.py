class InvalidFileException(Exception):
    """
    Raised when the Auto Integrate file does not have a valid header
    """
    pass

class FileParseException(Exception):
    """
    Raised when pandas cannot parse the csv file to a dataframe
    """
    pass

class TypeConversionException(Exception):
    """
    Raised when the Auto Integrate file does not have valid columns
    """
    pass
