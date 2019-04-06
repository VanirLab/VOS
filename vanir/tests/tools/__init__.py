import io
import sys

class StdoutBuffer(object):
    def __init__(self):
        self.stdout = io.StringIO()

    def __enter__(self):
        sys.stdout = self.stdout
        return self.stdout

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = sys.__stdout__
        return False
