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
Or you can use the "conda_env.yml" file to create an anaconda environment like this:<br>
Open you anaconda prompt (terminal) and navigate to the location of the "conda_env.yml" file.<br>
Then type:<br>

```shell
conda env create -f conda_env.yml
```
Don't forget to activate your new environment:
```shell
conda activate viewer
```

To start the Viewer, open your <i>terminal</i> of choice and go to the directory containing the files.<br>
Then run "main.py":<br>

```shell
python main.py
```

## Short cut for starting the app in Windows
You can use the "Start_RoiBaView.bat" file to quickly start the app. For this just double click the batch file. 
However, for it to work, you have to adjust some lines in the batch file.

Under "REM Path to the Python script directory" change:


<i> SET ANACONDA_PATH=*Your\Path\To\Anaconda\anaconda3* </i> (for Anaconda)

or

<i> SET ANACONDA_PATH=*Your\Path\To\Anaconda\miniconda3* </i> (for Miniconda)


If you don't know the path you can find it by opening the anaconda prompt and type:
```shell
where conda
```

Under "REM Name of the Anaconda environment" change to your anaconda environment:

SET ENV_NAME=*NameOfYourEnvironment*

Under "REM Path to the Python script directory" change to the directory of ROIBAVIEW:

SET SCRIPT_DIR=*Your\Path\To\RoiBaView*


## Import Data
You can import data from .csv files (comma separated).<br>
<i>File --> Import csv file ...</i><br>

The file has to have the following structure (with or without header, both works):<br>
| ROI_1         | ROI_2         | ... | ROI_n         |
|---------------|---------------|-----|---------------|
| x<sub>0</sub> | x<sub>0</sub> |     | x<sub>0</sub> |
| x<sub>1</sub> | x<sub>1</sub> |     | x<sub>1</sub> |
| : .           | : .           |     | : .           |
| x<sub>n</sub> | x<sub>n</sub> |     | x<sub>n</sub> |

Everytime you import a csv file you will be asked to enter the sampling rate in Hz.<br>

If the data file does not contain ROI based data, but traces that are the same for all ROIs (global) you can check the
"global data set" setting. Each Column will be treated as a data trace.<br>

The Viewer can only import files using "comma" (,) as separator. You can convert files using different separators like this:<br>
<i>Tools --> Convert csv files</i><br>
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
You can use the "Video Viewer" to display videos or tiff stacks.<br>
<i>Tools --> Open Video Viewer </i><br>
A new window will pop up.<br>
By clicking on "Connect to Data" you can connect the video with the plotted data to align them.

## Video Converter
RoiBaViewer provides a video converter based on ffmpeg (ffmpy).<br>
<i>Tools --> Open Video Converter </i><br>
To use it you must have "ffmpeg" installed.
You can visit https://ffmpeg.org/ to get it.
First time you open the video converter it will ask you to specify the directory of the ffmpeg.exe.


### ----------
Nils Brehm - 2024
