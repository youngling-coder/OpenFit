import json
import os
import random
import time
import csv
from copy import deepcopy
from typing import List, AnyStr, Dict, Union, Generator, Tuple

BASE_CONFIG = {
    "exercises": [],
    "playlist_source": "/home/nemo/Music",
    "assistant": {
        "model": "gpt-3.5-turbo",
        "token": ""
    }
}


CONFIG_FILENAME = os.path.expanduser("~/.config/OpenFit/config.json")


class ProgramData:
    def __init__(self):
        self.__config: Dict = {}
        self.__audios: List[str] = []

    def get_openai_token(self):
        return self.__config["assistant"]["token"]

    def set_assistant_model(self, model: AnyStr) -> None:
        self.__config["assistant"]["model"] = model
        self.write_config(CONFIG_FILENAME)

    def get_assistant_model(self) -> AnyStr:
        return self.__config["assistant"]["model"]

    def append_to_conversation(self, row: Tuple) -> None:

        if not isinstance(row, Tuple):
            row = tuple(row)

        if self.get_save_conversation_enabled():
            if os.path.exists(CONVERSATION_FILENAME):
                with open(CONVERSATION_FILENAME, mode="w") as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(row)
            else:

                with open(CONVERSATION_FILENAME, mode="w") as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(["author", "timestamp", "content"])

                self.append_to_conversation(row)

    def remove_audio(self, index: int) -> None:
        """
        Remove an audio file from the playlist at the specified index.

        :param index: The index of the audio file to remove. (int)
        """

        self.__audios.pop(index)

    def get_audios(self) -> List[str]:
        """
        Get a list of audio files in the playlist.

        :return: A list containing the paths of audio files in the playlist. (List[str])
        """

        return self.__audios

    def shuffle_playlist(self) -> None:
        """
        Shuffle the audio files in the playlist randomly.
        """

        random.seed(time.time())
        random.shuffle(self.__audios)

    def __reload_playlist(self) -> None:
        """
        Reload the playlist by updating the internal audio list.

        This method clears the existing audio list and repopulates it based on the audio files found in the playlist directory.
        """
        self.__audios = []

        # Check if the playlist directory exists
        if os.path.exists(self.get_playlist_path()):
            # Iterate through each audio file in the playlist directory
            for audio in os.listdir(self.get_playlist_path()):
                audio = os.path.join(self.get_playlist_path(), audio)
                # Check if the file exists and has a .mp3 extension
                if os.path.exists(audio) and audio.lower().endswith(".mp3"):
                    self.__audios.append(audio)

            # Sort the list of audio files alphabetically
            self.__audios = sorted(self.__audios)

    def load_config(self, filename: AnyStr) -> None:
        """
        Load the configuration from a file into a dictionary object.

        :param filename: The name of the file to load the configuration from. (AnyStr)
        """

        # Read the configuration from the specified file
        with open(filename) as json_config:
            self.__config = json.load(json_config)

        # Reload the playlist after loading the configuration
        self.__reload_playlist()

    def write_config(self, filename: AnyStr, config: Dict = None) -> None:
        """
        Write the existing config dictionary object to a file.

        :param filename: The name of the file to write the configuration to. (AnyStr)
        :param config: The dictionary containing the configuration to write. If None, the current config object will be used.
                       (Optional[Dict])

        If the `config` parameter is not provided, the method will attempt to use the existing config. If the existing
        config is not available, it will use the base config.

        The configuration will be written to the specified file with an indentation of 4 spaces.
        """

        if not config:
            if self.__config:
                config = self.__config
            else:
                config = BASE_CONFIG

        # Write the new config to the file
        with open(filename, "w") as json_config:
            json.dump(config, json_config, indent=4)

    def remove_exercise(self, at: int) -> None:
        """
        Remove an exercise at the specified index.

        :param at: The index of the exercise to remove. (int)
        """

        self.__config["exercises"].pop(at)
        self.write_config(CONFIG_FILENAME)

    def exercise_at(self, index: int) -> Dict:
        """
        Retrieve a copy of the exercise at the specified index.

        :param index: The index of the exercise to retrieve. (int)

        :return: A dictionary containing the exercise information, or an empty dictionary if the index is out of range.
        """

        return self.__config["exercises"][index].copy()

    def index_of_exercise(self, name: str) -> Union[int, None]:
        """
        Search for an exercise index by the given name.

        :param name: The name of the exercise to search for. (str)

        :return: An index of the found task or None if task not found.
        """

        for idx in range(len(self.__config["exercises"])):
            if self.__config["exercises"][idx]["name"].lower() == name.lower():
                return idx

        return

    def get_exercises(self) -> List[Dict]:
        """
        Get a deep copy of the list of exercises.

        :return: A list containing dictionaries representing exercises. (List[Dict])
        """

        return deepcopy(self.__config["exercises"])

    def get_playlist_path(self) -> AnyStr:
        """
        Get the path to the playlist source directory.

        :return: The path to the playlist source directory. (AnyStr)
        """

        return self.__config["playlist_source"]

    def set_playlist_path(self, path: AnyStr) -> None:
        """
        Set the path to the playlist source directory.

        :param path: The new path to set. (AnyStr)
        """

        self.__config["playlist_source"] = path

        self.__reload_playlist()

        # Write the updated configuration to file
        self.write_config(CONFIG_FILENAME)

    def add_exercise(self, exercise: Dict) -> None:
        """
        Add a new exercise to the configuration.

        :param exercise: A dictionary containing the details of the exercise to add. (Dict)

        If all values in the provided exercise dictionary are truthy, the method checks if an exercise with the same name
        already exists. If not, it appends the new exercise to the list of exercises. Otherwise, it raises a ValueError.

        After adding the exercise, the updated configuration is written to file.
        """
        if all(exercise.values()):
            if self.index_of_exercise(exercise["name"]) is None:
                return self.__config["exercises"].append(exercise)
            else:
                raise ValueError(f"Task with name \"{exercise['name']}\" already exists!")

        self.write_config(CONFIG_FILENAME)

    def update_exercise(self, index: int, u_exercise: Dict) -> None:
        """
        Update an existing exercise in the configuration.

        :param index: The index of the exercise to update. (int)
        :param u_exercise: A dictionary containing the updated details of the exercise. (Dict)

        The method retrieves the exercise at the specified index and updates its attributes based on the provided
        u_exercise dictionary. Only attributes with truthy values in the u_exercise dictionary are updated.

        After updating the exercise, the updated configuration is written to file.
        """
        exercise = self.__config["exercises"][index]

        for key, value in u_exercise.items():
            if value:
                exercise[key] = value

        self.write_config(CONFIG_FILENAME)
