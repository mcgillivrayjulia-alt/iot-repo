Hi! These are the files from my midterm and final projects.

Midterm: PLANTSENSE
Runs a tempterature, moisture, and light sensor, and feeds the data into an html for live display using Flask. Sends an email when any value reaches above a certain threshold.
You need the following file directory:
FOLDER: plantsense --> plantsense.py
                       FOLDER: templates --> plantsense.html

FINAL: TRACE UAV
Runs two gas sensors and a camera off of the code, feeds it into the html for live display. Logs all of the data into a csv, and saves the picture into a folder. Sends an email when the gas reaches above a certain level.
You need the following file directory:
FOLDER: traceuav --> traceuav.py
                     FOLDER: templates --> traceuav.html

*You will need to change the directory of your pi. You can also have trace uav run on boot by creating a systemctl in the terminal.
