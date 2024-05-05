from typing import List, Iterable


class Exercise:
    def __init__(self, exercise: dict):
        # Validate exercise parameters
        self.__validate_params(exercise)

        self.__required_params = [
            "name", "type", "reps", "sets", "days"
        ]

        self.__load_attrs_from_dict(exercise)

    def __load_attrs_from_dict(self, exercise, update: bool = False):
        for key, value in exercise.items():
            if not value:
                if update:
                    continue
                else:
                    raise ValueError(f"{key} value for Exercise is not specified but required.")
            setattr(self, f"__{key}", value)

    @property
    def name(self):
        return self.__name

    @name.setter
    def name(self, __value: str):
        self.__name = __value

    @property
    def type(self):
        return self.__type

    @type.setter
    def type(self, __value: str):
        self.__type = __value

    @property
    def reps(self):
        return self.__reps

    @reps.setter
    def reps(self, __value: int):
        self.__reps = __value

    @property
    def sets(self):
        return self.__sets

    @sets.setter
    def sets(self, __value: int):
        self.__sets = __value

    @property
    def days(self):
        return self.__days

    @days.setter
    def days(self, __value: Iterable[str]):
        self.__days = __value

    def __validate_params(self, exercise):
        for param in self.__required_params:
            if param not in exercise:
                raise ValueError(f"Parameter '{param}' is missing in the dictionary.")

    def to_dict(self):
        attributes = {}
        for attr_name in dir(self):
            if not attr_name.startswith('__') and not callable(getattr(self, attr_name)):
                attributes[attr_name] = getattr(self, attr_name)
        return attributes

    def update(self, exercise):
        self.__load_attrs_from_dict(exercise, update=True)
