# RoiBaView
Welcome to the <i>RoiBaView</i>.
With this viewer you can plot and analyze signals from different kinds of experiments (e.g. Calcium Imaging).

## Installation
Before running the "main.py" file you should make sure that you have installed all the needed dependencies.
You can manually install the dependencies via pip or conda (Anaconda) like this:

```shell
pip install numpy
pip install pandas
pip install scipy
pip install ipython
pip install PyQt6
pip install pyqtgraph
pip install opencv-python
pip install ffmpy
pip install h5py
pip install tifffile
```
Or you can use the "conda_env.yml" file to create an anaconda environment like this:\
Open you anaconda prompt (terminal) and navigate to the location of the "conda_env.yml" file.\
Then type:

```shell
conda env create -f conda_env.yml
```
Don't forget to activate your new environment:
```shell
conda activate viewer
```

To start the Viewer, open your <i>terminal</i> of choice and go to the directory containing the files.
Then run "main.py":

```shell
python main.py
```

## Import Data
You can import data from .csv files (comma separated).
<i>File --> Import csv file ...</i>

The file has to have the following structure (with or without header, both works):
| ROI_1         | ROI_2         | ... | ROI_n         |
|---------------|---------------|-----|---------------|
| x<sub>0</sub> | x<sub>0</sub> |     | x<sub>0</sub> |
| x<sub>1</sub> | x<sub>1</sub> |     | x<sub>1</sub> |
| : .           | : .           |     | : .           |
| x<sub>n</sub> | x<sub>n</sub> |     | x<sub>n</sub> |

Everytime you import a csv file you will be asked to enter the sampling rate in Hz.

If the data file does not contain ROI based data, but traces that are the same for all ROIs (global) you can check the
"global data set" setting. Each Column will be treated as a data trace.

The Viewer can only import files using "comma" (,) as separator. You can convert files using different separators like this:
<i>Tools --> Convert csv files</i>
- Select the File
- Specify the separator of this file
- Specify the desired separator for the output file

## Plotting Data
If you successfully imported a new data set, it will be displayed in the list on the left side of the main window.
By left-clicking on the data set, you can activate it. Right-clicking will open up a context menu with several options for
modifying this data set.

## Peak Detection
If you have activated a data set, you can press on "Detect Peaks" to start the peak detection mode.
A range of different settings will appear and a live detection will be shown in the main window.
By clicking on "Export" you can save a .csv file containing information about the detected peaks of this trace.


## Video Viewer
You can use the "Video Viewer" to display videos or tiff stacks.
<i>Tools --> Open Video Viewer </i>
A new window will pop up.
By clicking on "Connect to Data" you can connect the video with the plotted data to align them.

## Video Converter
RoiBaViewer provides a video converter based on ffmpeg (ffmpy).
<i>Tools --> Open Video Converter </i>
To use it you must have "ffmpeg" installed. 
You can visit https://ffmpeg.org/ to get it.
First time you open the video converter it will ask you to specify the directory of the ffmpeg.exe.


### ----------
Nils Brehm - 2024
