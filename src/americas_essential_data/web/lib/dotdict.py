class DotDict:
    """Class that converts a dictionary to an object with dot notation access"""

    def __init__(self, data):
        for key, value in data.items():
            if isinstance(value, dict):
                value = DotDict(value)
            setattr(self, key, value)
