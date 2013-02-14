"""This module contains extra low level definitons for use in lower loops."""

class BadModelPointError(Exception):
    """Exception raised for errors believed to be due to a bad model point.
    
    When this exception is raised pysusy will exit the current iteration of
    the main scan loop and skip to the next point.
    
    Attributes:
        msg -- explanation of the error
    """
    
    def __init__(self, msg):
        self.msg = msg
        
    def __str__(self):
        return repr(self.msg)
