import os
import time
import pandas as pd
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QFileDialog, QDialog, QMessageBox, QApplication
from roibaview.gui import SimpleInputDialog


class CSVHandler:
    def __init__(self, main_window):
        self.main_window = main_window

    def open_file_dialog(self):
        input_file, _ = QFileDialog.getOpenFileName(
            self.main_window, "Select Input File", "", "csv file (*.csv; *.txt)")

        if input_file:
            # Read csv file to memory
            df = pd.read_csv(input_file)
            return df, input_file
        return None

    def drop_column(self, df, col_nr):
        # Remove the column
        df = df.drop(df.columns[col_nr], axis=1)
        return df

    def remove_column_from_csv_file(self):
        # Open the file
        df, file_dir = self.open_file_dialog()

        # Get Column Nr
        dialog = SimpleInputDialog(title='Settings', text='Please enter some stuff: ')
        if dialog.exec() == QDialog.DialogCode.Accepted:
            received = dialog.get_input()
        else:
            return None

        col_nr = int(received)
        # Remove the column
        df = self.drop_column(df, col_nr=col_nr)

        # Create a non-modal message box
        message_box = QMessageBox(self.main_window)
        message_box.setWindowTitle("Saving...")
        message_box.setText("The file is being saved. Please wait.")
        message_box.setStandardButtons(QMessageBox.StandardButton.NoButton)  # Disable buttons
        message_box.show()

        # Store to HDD
        base_dir = os.path.split(file_dir)[0]
        file_name = os.path.split(file_dir)[1][:-4]
        df.to_csv(f'{base_dir}/{file_name}_new.csv', index=False, header=None)

        message_box.destroy()
        # message_box.setText("The file has been saved successfully!")
        # message_box.setStandardButtons(QMessageBox.StandardButton.Ok)  # Disable buttons
        QMessageBox.information(self.main_window, "Save Complete", "The file has been saved successfully!")


