# RoiBaView
Welcome to the <i>RoiBaView</i>.
With the <i>CaEventViewer</i> you can plot and analyze calcium transients from Ca-imaging experiments.

## Installation
Before running the "main.py" file you should make sure that you have installed all the needed dependencies.
You can manually install the dependencies via pip or conda (Anaconda) like this:

```shell
pip install numpy
pip install pandas
pip install scipy
pip install PyQt6
pip install pyqtgraph
pip install opencv-python
pip install ffmpy
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


### ----------
Nils Brehm - 2024
