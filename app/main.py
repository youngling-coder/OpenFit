# PyQt5 imports
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTableWidgetItem, QListWidgetItem, QMessageBox, QFileDialog)
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent, QMediaPlaylist
from PyQt5.QtCore import Qt, QUrl, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap

from app_ui import Ui_MainWindow

from typing import List, AnyStr, Dict, Union
from datetime import datetime
from openai import OpenAI
import sys
import os

# Application modules
from program_data import ProgramData, CONFIG_FILENAME
from audioinfo import get_audio_name
from functime import prettify_time, milliseconds_to_seconds


class AssistantWorker(QThread):
    answer_received = pyqtSignal(str)
    answer_finished = pyqtSignal(str)

    def __init__(self, token: AnyStr, model: AnyStr):
        super().__init__()
        self.__token = token

        self.client = OpenAI(
            api_key=self.__token
        )

        self.chat_history = [
            {
                "role": "system",
                "content": """
You are the sports coach for newbies and amateurs.
If you are asked about sports or health, you must answer in detail.
You must give advice and answer questions using only simple expressions and terms.
Different people can talk to you, so if you do not have specific information about the person you are talking to,
you should only give general advice. If you are asked about anything other than sport,
you must explain that you are only communicating on topics related to sport and a healthy lifestyle.
        """
            }
        ]
        self.__model = model

        self.__question = ""

    def set_model(self, model: AnyStr) -> None:
        self.__model = model

    def set_question(self, value: str) -> None:
        self.__question = str(value)

    def run(self):

        if self.__question:

            self.chat_history.append(
                {
                    "role": "user",
                    "content": self.__question
                }
            )
            stream = self.client.chat.completions.create(
                model=self.__model,
                messages=self.chat_history,
                stream=True,
                response_format={"type": "text"}
            )

            now = datetime.now()
            timestamp = now.strftime("%d.%m.%Y %I:%M %p")
            answer_html = f"""
            <p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">
                <span style=" font-size:8pt;">{timestamp}<br /></span>
                <img src=":/tab/img/user.png" width="15" />
                {self.__question}
            </p><br />"""
            self.answer_received.emit(answer_html)

            answer_html = f"""
            <p style="margin-top: 0px; margin-bottom: 0px; margin-left: 0px; margin-right: 0px; -qt-block-indent: 0; text-indent: 0px;">
                <span style=" font-size:8pt;">{timestamp}<br /></span>
                <img src=":/tab/img/assistant.png" width="15" >
            """

            answer = ""
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    answer += chunk.choices[0].delta.content

            answer_html += f"{answer}</p><br />".replace("\n", "<br \\>")
            self.answer_received.emit(answer_html)

            self.chat_history.append(
                {
                    "role": "assistant",
                    "content": answer
                }
            )


class WorkItOut(QMainWindow):
    def __init__(self, pd: ProgramData):
        super(WorkItOut, self).__init__()

        # Setting up program data
        self.program_data = pd

        # Setting up necessary variables
        self.ui = Ui_MainWindow()
        self.assistant = AssistantWorker(
            token=self.program_data.get_openai_token(),
            model=self.program_data.get_assistant_model()
        )
        self.media_player = QMediaPlayer()
        self.media_playlist = QMediaPlaylist()

        self.filter_exercises_by_day = lambda exercise: self.today.strftime("%A") in exercise["days"]
        self.shown_exercises: list = []
        self.today = datetime.now()
        self.search_query: str = ""
        self.search_categories = [
            "Name",
            "Type",
            "Reps",
            "Sets",
            "Days"
        ]
        self.table_headers = self.search_categories
        self.show_all_exercises_check_state = Qt.CheckState.Unchecked
        formatted_date = self.today.strftime("%A, %B %d")

        # Setting up UI
        self.ui.setupUi(self)

        # Write today's date
        self.ui.dateLabel.setText(formatted_date)

        # Loading exercises to UI elements
        self.loadExercisesToUI()

        # Load assistant model to UI
        self.ui.assistanModelEdit.setText(self.program_data.get_assistant_model())

        # Setup media player and playlist to play music
        self.media_player.setPlaylist(self.media_playlist)
        self.media_player.setVolume(self.ui.volumeSlider.value())

        # Loading audio list to UI
        self.reloadPlaylist()

        # Setup first track as current if there is any audios
        if self.program_data.get_audios():
            self.ui.currentAudioLabel.setText(get_audio_name(self.program_data.get_audios()[0])[:15])

        # Add search categories
        self.ui.searchCategoryComboBox.addItems(self.search_categories)

        # Assistant: Connecting signals to slots
        self.assistant.answer_received.connect(self.updateAssistantAnswer)
        self.assistant.answer_finished.connect(self.assistantAnswerFinished)

        # Tabs TRAINING, MANAGE: Connecting signals to slots
        self.ui.showAllExercisesCheckBox.stateChanged.connect(self.showAllExercisesCheckBoxStateChanged)
        self.ui.searchExercisesEdit.textEdited.connect(self.filterExercises)
        self.ui.searchCategoryComboBox.currentTextChanged.connect(self.filterExercises)
        self.ui.addEditExerciseButton.clicked.connect(self.addEditExerciseButtonClicked)
        self.ui.deleteExerciseButton.clicked.connect(self.deleteExerciseButtonClicked)
        self.ui.exercisesListWidget.currentItemChanged.connect(self.exercisesListWidgetCurrentItemChanged)
        self.ui.selectExistingExerciseComboBox.currentIndexChanged.connect(
            self.selectExistingExerciseComboBoxCurrentIndexChanged
        )

        # Tab PLAYER: Connecting signals to slots
        self.ui.playPauseAudioButton.clicked.connect(self.mediaPlayerStateChanged)
        self.ui.volumeSlider.valueChanged.connect(self.setVolume)
        self.ui.previousAudioButton.clicked.connect(self.playPrevious)
        self.ui.nextAudioButton.clicked.connect(self.playNext)
        self.ui.reloadPlaylistButton.clicked.connect(
            lambda _: self.reloadPlaylist()
        )
        self.media_playlist.currentMediaChanged.connect(self.currentAudioChanged)
        self.media_player.positionChanged.connect(self.updateDuration)
        self.ui.musicPlaylistListWidget.itemDoubleClicked.connect(self.setCurrentAudioFromPlaylistListWidget)
        self.ui.shuffleAudioButton.clicked.connect(self.shuffleAudioButtonClicked)
        self.ui.setMusicPlaylistFolderButton.clicked.connect(self.setMusicPlaylistButtonFolderClicked)

        # Tab ASSISTANT: Connecting signals to slots
        self.ui.askAssistantButton.clicked.connect(self.askAssistantButtonClicked)

    def assistantAnswerFinished(self, answer):
        # Handle AI assistant answer and insert it to the UI
        self.ui.assistantAnswerArea.insertHtml(answer)

    def updateAssistantAnswer(self, answer_html):
        # Handle AI assistant answer and insert it to the UI
        self.ui.assistantAnswerArea.insertHtml(answer_html)

    def askAssistantButtonClicked(self):
        # Send user question to AI assistant
        question = self.ui.userQuestionEdit.text().strip()
        if question:
            self.assistant.set_question(question)
            self.ui.userQuestionEdit.clear()
            self.assistant.start()

    def resizeEvent(self, a0):
        """
        Event handler for resizing the window.

        :param a0: Resize event.
        """

        a0.accept()

        width = self.ui.exercisesTableWidget.width()
        self.ui.exercisesTableWidget.horizontalHeader().setDefaultSectionSize(int(width / 6))

    def reloadPlaylist(self, source: AnyStr = None, shuffle: bool = False) -> None:
        """
        Reloads the playlist with optional shuffling.

        :param source: Optional source to set the playlist path.
        :param shuffle: Boolean indicating whether to shuffle the playlist.
        """

        if shuffle:
            self.program_data.shuffle_playlist()
        else:
            if source:
                self.program_data.set_playlist_path(source)
            self.ui.musicPlaylistFolderEdit.setText(self.program_data.get_playlist_path())
        self.loadMediaContent()
        self.ui.playPauseAudioButton.setIcon(QIcon(":/ui/img/play.png"))
        self.loadPlaylistToUI()

    def showMessageBox(self, msgbox: QMessageBox, answer: bool = False,
                       expecting_answer: QMessageBox.StandardButton = QMessageBox.StandardButton.Yes) -> Union[bool, None]:
        """
        Display a message box and optionally return the user's response.

        :param msgbox: QMessageBox object to display.
        :param answer: Boolean indicating whether to return the user's response. (Default: False)
        :param expecting_answer: Expected QMessageBox.StandardButton value. (Default: QMessageBox.StandardButton.Yes)
        :return: User's response if 'answer' is True, otherwise None.
        """

        clicked_button = msgbox.exec_()

        if answer:
            return clicked_button == expecting_answer

        return

    def setMusicPlaylistButtonFolderClicked(self) -> None:
        """
        Event handler for clicking the set music playlist button.
        Opens a file dialog to select the music playlist folder and reloads the playlist accordingly.
        """

        dialog = QFileDialog()
        dialog.setFileMode(dialog.DirectoryOnly)
        if dialog.exec_():
            source = dialog.selectedFiles()[0]
            self.reloadPlaylist(source)

    def shuffleAudioButtonClicked(self) -> None:
        """
        Event handler for clicking the shuffle audio button.
        Shuffles the audio playlist and starts playing.
        """

        if self.program_data.get_audios():
            self.reloadPlaylist(shuffle=True)
            self.media_player.play()
            self.ui.playPauseAudioButton.setIcon(QIcon(":/ui/img/pause.png"))

    def playAudio(self, index: int) -> None:
        """
        Play audio at the specified index in the playlist.

        :param index: Index of the audio to play.
        """

        if os.path.exists(self.program_data.get_audios()[index]):
            self.media_playlist.setCurrentIndex(index)
            self.media_player.play()
            self.ui.playPauseAudioButton.setIcon(QIcon(":/ui/img/pause.png"))
        else:
            self.ui.musicPlaylistListWidget.takeItem(index)
            self.program_data.remove_audio(index)
            self.ui.musicPlaylistListWidget.setCurrentRow(index)
            self.setCurrentAudioFromPlaylistListWidget()

    def setCurrentAudioFromPlaylistListWidget(self) -> None:
        """
        Set the currently selected audio from the playlist widget and play it.
        """

        index = self.ui.musicPlaylistListWidget.currentRow()
        self.playAudio(index)

    def updateDuration(self) -> None:
        """
        Update the duration labels and progress bar for the currently playing audio.
        """

        position = milliseconds_to_seconds(self.media_player.position())
        duration = milliseconds_to_seconds(self.media_player.duration())

        position_str = prettify_time(position)
        duration_str = prettify_time(duration)

        if (duration > 0 and
                self.ui.audioDurationProgressBar.maximum() != milliseconds_to_seconds(
                    self.media_player.duration())):
            self.ui.audioDurationProgressBar.setMaximum(
                milliseconds_to_seconds(self.media_player.duration()))

        self.ui.audioPositionLabel.setText(f"{position_str}")
        self.ui.audioDurationLabel.setText(f"{duration_str}")
        self.ui.audioDurationProgressBar.setValue(position)

    def currentAudioChanged(self) -> None:
        """
        Update UI when the currently playing audio changes.
        """

        path = self.media_playlist.currentMedia().canonicalUrl().path()

        if os.path.exists(path):
            audio_name = get_audio_name(path)

            self.ui.audioDurationProgressBar.setValue(0)

            if not audio_name:
                audio_name = "No tracks"
            self.ui.currentAudioLabel.setText(audio_name)

    def playNext(self) -> None:
        """
        Play the next audio in the playlist.
        """

        if self.program_data.get_audios():
            self.media_playlist.setCurrentIndex(self.media_playlist.nextIndex())

    def playPrevious(self) -> None:
        """
        Play the previous audio in the playlist.
        """

        if self.program_data.get_audios():
            self.media_playlist.setCurrentIndex(self.media_playlist.previousIndex())

    def setVolume(self) -> None:
        """
        Set the volume level and update the volume icon accordingly.
        """

        volume = self.ui.volumeSlider.value()
        self.media_player.setVolume(volume)

        volume_level = volume // 33

        match volume_level:
            case 0:
                self.ui.volumeImage.setPixmap(QPixmap(":/ui/img/speaker-low.png"))
            case 1:
                self.ui.volumeImage.setPixmap(QPixmap(":/ui/img/speaker-medium.png"))
            case 2:
                self.ui.volumeImage.setPixmap(QPixmap(":/ui/img/speaker-high.png"))

    def loadPlaylistToUI(self) -> None:
        """
        Load the playlist to the user interface.

        Clears the music playlist list widget and populates it with tracks from the program data.
        """
        self.ui.musicPlaylistListWidget.clear()
        for track in self.program_data.get_audios():
            track_item = QListWidgetItem(get_audio_name(track))
            track_item.setIcon(QIcon(":/file/img/music-file.png"))
            self.ui.musicPlaylistListWidget.addItem(track_item)

    def loadMediaContent(self) -> None:
        """
        Load media content into the media playlist.

        Clears the media playlist and adds media content from the program data.
        """
        self.media_playlist.clear()
        for track in self.program_data.get_audios():
            media = QMediaContent(QUrl.fromLocalFile(track))
            self.media_playlist.addMedia(media)

        self.media_playlist.setCurrentIndex(0)

    def mediaPlayerStateChanged(self) -> None:
        """
        Handle changes in media player state.

        If there are audio tracks available,
        toggles between playing and pausing the media player and updates the UI accordingly.
        """

        if self.program_data.get_audios():
            if self.media_player.state() == QMediaPlayer.State.PlayingState:
                self.media_player.pause()
                self.ui.playPauseAudioButton.setIcon(QIcon(":/ui/img/play.png"))
            else:
                self.media_player.play()
                self.ui.playPauseAudioButton.setIcon(QIcon(":/ui/img/pause.png"))

    def selectExistingExerciseComboBoxCurrentIndexChanged(self) -> None:
        """
        Handle the current text changed event of the "Select Existing Exercise" combo box.

        This method is triggered when the user selects a different exercise from the combo box.
        It retrieves the selected exercise by name from the configuration data and fills the exercise form in the UI.

        :return: None
        """

        name = self.ui.selectExistingExerciseComboBox.currentText()
        exercise_index = self.program_data.index_of_exercise(name)
        if not (exercise_index is None):
            self.fillExerciseForm(self.program_data.exercise_at(exercise_index))

    def fillExerciseForm(self, exercise: Dict = None) -> None:
        """
        Fill the exercise form with specified exercise data,
        or set all fields to default values if no exercise is provided.

        :param exercise: Dictionary containing exercise data. (Optional)
        """

        if exercise:
            self.ui.exerciseNameEdit.setText(exercise["name"])
            self.ui.exerciseTypeEdit.setText(exercise["type"])
            self.ui.exerciseRepeatsSpinBox.setValue(exercise["reps"])
            self.ui.exerciseSetsSpinBox.setValue(exercise["sets"])
            self.ui.exerciseDaysEdit.setText(", ".join(exercise["days"]))
        else:
            self.ui.searchCategoryComboBox.setCurrentIndex(0)
            self.ui.exerciseNameEdit.clear()
            self.ui.exerciseTypeEdit.clear()
            self.ui.exerciseRepeatsSpinBox.setValue(8)
            self.ui.exerciseSetsSpinBox.setValue(2)
            self.ui.exerciseDaysEdit.clear()

    def exercisesListWidgetCurrentItemChanged(self) -> None:
        """
        Set the current exercise depending on the selected element in the exercisesListWidget.
        """

        index = self.ui.exercisesListWidget.currentRow()
        self.ui.selectExistingExerciseComboBox.setCurrentIndex(index + 1)

    def deleteExerciseButtonClicked(self) -> None:
        """
        Deletes the selected exercise.

        :return: None
        """

        if self.ui.exercisesListWidget.currentItem():
            name = self.ui.exercisesListWidget.currentItem().text()
            index = self.program_data.index_of_exercise(name)

            is_proceed = self.showMessageBox(
                msgbox=QMessageBox(
                    QMessageBox.Icon.Warning,
                    "Attention!",
                    f"Are you sure you want to delete the exercise \"{name}\"? "
                    "If the answer is \"Yes\", changes will be applied immediately.",
                    QMessageBox.Yes | QMessageBox.Cancel
                ),
                answer=True
            )

            if index and is_proceed:
                self.program_data.remove_exercise(index)

            self.loadExercisesToUI()

    def addEditExerciseButtonClicked(self) -> None:
        """
        Adds new exercise to the exercises list, or edit exercise attributes if it is already exists.
        :return: None
        """

        days = self.ui.exerciseDaysEdit.text().split(",")
        days = list(map(lambda day: day.lstrip(), days))
        days = list(filter(lambda day: day, days))
        exercise = {
            "name": self.ui.exerciseNameEdit.text().lstrip(),
            "type": self.ui.exerciseTypeEdit.text().lstrip(),
            "reps": self.ui.exerciseRepeatsSpinBox.value(),
            "sets": self.ui.exerciseSetsSpinBox.value(),
            "days": days
        }

        if self.ui.selectExistingExerciseComboBox.currentIndex() != 0:
            name = self.ui.selectExistingExerciseComboBox.currentText()
            index = self.program_data.index_of_exercise(name)
            self.program_data.update_exercise(index, exercise)
        else:
            try:
                self.program_data.add_exercise(exercise)
            except ValueError:
                self.showMessageBox(
                    msgbox=QMessageBox(
                        QMessageBox.Icon.Critical,
                        "Error!",
                        "Could not add new exercise, because an exercise with such name is already exists. "
                        "To edit existing exercise select it from the dropdown list. "
                        "If you are about to add new exercise, try to edit name.",
                        QMessageBox.Ok
                    )
                )

        self.loadExercisesToUI()

    def filterExercises(self) -> None:
        """
        Search exercises based on user search query and category.

        This method retrieves exercises based on the user's search query and selected category from the UI.
        It updates the list of shown exercises accordingly and fills the exercises table in the UI.

        :return: None
        """
        category = self.ui.searchCategoryComboBox.currentText().lower()

        def filter_by_category(query: AnyStr, exercises: List[Dict]) -> List[Dict]:
            """
            Filter exercises by category.

            :param query: Category to filter by.
            :param exercises: List of exercises to filter.
            :return: Filtered list of exercises.
            """

            return list(filter(lambda exercise:
                               query in str(exercise[category]).lower() or query == str(exercise[category]).lower(),
                               exercises))

        def uniquify(exercises: List[Dict]) -> List[Dict]:
            """
            Remove duplicates from a list of exercises.

            :param exercises: List of exercises.
            :return: List of exercises with duplicates removed.
            """

            exercises_hash_map = {}

            for exercise in exercises:
                exercises_hash_map[exercise["name"]] = exercise

            return list(exercises_hash_map.values())

        self.shown_exercises = []
        self.search_query = self.ui.searchExercisesEdit.text().lstrip()

        if self.search_query and self.ui.searchCategoryComboBox.currentIndex() != 0:
            if category in ["days", "type"]:
                self.shown_exercises = []
                for item in self.search_query.split(","):
                    item = item.lstrip()
                    self.shown_exercises.extend(filter_by_category(item, self.program_data.get_exercises()))

                self.shown_exercises = uniquify(self.shown_exercises)
            else:
                self.shown_exercises = filter_by_category(self.search_query, self.program_data.get_exercises())
        else:
            self.shown_exercises = self.program_data.get_exercises()

        self.fillExercisesTable(self.shown_exercises)

    def showAllExercisesCheckBoxStateChanged(self) -> None:
        """
        Handle the state change of the "Show All Exercises" check box.

        This method is triggered when the state of the "Show All Exercises" check box is changed.
        It updates the list of shown exercises based on whether the checkbox is checked or unchecked,
        and fills the exercises table accordingly.

        :return: None
        """

        self.show_all_exercises_check_state = self.ui.showAllExercisesCheckBox.isChecked()

        if not self.show_all_exercises_check_state:
            self.shown_exercises = list(filter(self.filter_exercises_by_day, self.program_data.get_exercises()))
        else:
            self.shown_exercises = self.program_data.get_exercises()
        self.fillExercisesTable(self.shown_exercises)

    def fillExercisesTable(self, exercises: list) -> None:

        """
        Fill the exercises table with the provided list of exercises.

        This method populates the exercises table in the UI with the provided list of exercises.
        Each exercise is represented as a row in the table, with columns for exercise name, type, reps, sets, and days.

        :param exercises: A list of dictionaries representing exercises, each containing exercise information.
                          The exercise dictionaries should have keys 'name', 'type', 'reps', 'sets', and 'days'.
                          Example:
                          [
                              {
                                  'name': 'Push-Ups',
                                  'type': 'Strength',
                                  'reps': 10,
                                  'sets': 3,
                                  'days': ['Monday', 'Wednesday', 'Friday']
                              },
                              {
                                  'name': 'Squats',
                                  'type': 'Strength',
                                  'reps': 8,
                                  'sets': 4,
                                  'days': ['Monday', 'Thursday']
                              },
                              ...
                          ]

        :return: None
        """

        # Reset table rows
        self.ui.exercisesTableWidget.setHorizontalHeaderLabels(self.table_headers)
        self.ui.exercisesTableWidget.setRowCount(len(exercises))

        for row, exercise in enumerate(exercises):
            # Add rows to the table
            self.ui.exercisesTableWidget.setItem(row, 0, QTableWidgetItem(exercise['name']))
            self.ui.exercisesTableWidget.setItem(row, 1, QTableWidgetItem(exercise['type']))
            self.ui.exercisesTableWidget.setItem(row, 2, QTableWidgetItem(str(exercise['reps'])))
            self.ui.exercisesTableWidget.setItem(row, 3, QTableWidgetItem(str(exercise['sets'])))
            self.ui.exercisesTableWidget.setItem(row, 4, QTableWidgetItem(', '.join(exercise['days'])))
            item = QTableWidgetItem()
            item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.ui.exercisesTableWidget.setItem(row, 5, item)

    def loadExercisesToUI(self) -> None:
        """
        Load exercises data to the user interface.

        This method loads exercise data to the user interface.
        It filters exercises based on the current day, fills the exercises table,
        and populates other UI elements such as list widgets and combo boxes with exercise names.

        :return: None
        """

        self.ui.exercisesListWidget.clear()
        self.ui.exercisesTableWidget.clear()
        self.ui.selectExistingExerciseComboBox.clear()
        self.ui.selectExistingExerciseComboBox.addItem("Select existing exercise to edit")

        self.shown_exercises = list(filter(self.filter_exercises_by_day, self.program_data.get_exercises()))
        self.fillExercisesTable(self.shown_exercises)
        for row, exercise in enumerate(self.program_data.get_exercises()):
            # Fill other UI elements
            self.ui.exercisesListWidget.addItem(exercise["name"])
            self.ui.selectExistingExerciseComboBox.addItem(exercise["name"])


if __name__ == "__main__":
    app = QApplication([])

    program_data = ProgramData()
    if os.path.exists(CONFIG_FILENAME):
        program_data.load_config(CONFIG_FILENAME)
    else:
        program_data.write_config(CONFIG_FILENAME)

    main_window = WorkItOut(program_data)
    main_window.show()

    sys.exit(app.exec_())
