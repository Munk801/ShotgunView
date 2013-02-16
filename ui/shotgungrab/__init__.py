#!/usr/bin/python
# =============================================================================
# $Id$
# =============================================================================
# Tool: sggetfromplaylist
# Contacts: Stephen Lu (slu)
#           Pipeline, Rhythm & Hues Studios
# =============================================================================
"""___DESC___

Tool that integrates with the Shotgun Pipeline Toolset.  This tool will retrieve
all the versions for a particular playlist and downloaded anything residing in
these versions.  
"""
# non-R&H imports
import os
import os.path
import sys
from parsedatetime import parsedatetime as dt
from parsedatetime import parsedatetime_consts as dt_consts
from time import mktime
from datetime import datetime
from shotgun_api3 import Shotgun
from urllib2 import urlopen
from PyQt4 import QtGui, QtCore

# R&H imports
import rh.argument
import rh.logutils.options

class SGInterface(QtGui.QWidget):
    def __init__(self):
        super(SGInterface, self).__init__()
        self.orgByScene = False
        self.initUI()

    def setModel(self, model, stringList):
        model.setStringList(stringList)
        
    def initUI(self):
        
        self.model = QtGui.QStringListModel()
        
        self.playlistNames = QtCore.QStringList()
        
        self.completer = QtGui.QCompleter(self.playlistNames)
        self.completer.setCaseSensitivity(0)
        
        # Labels
        lblUrl = QtGui.QLabel('Shotgun Server')
        lblScript = QtGui.QLabel('Script Name')
        lblApiKey = QtGui.QLabel('API Key')
        self.sgurl = QtGui.QLineEdit(self)
        self.sgscript = QtGui.QLineEdit(self)
        self.sgapikey = QtGui.QLineEdit(self)
        
        # Playlist download info
        lblplaylist = QtGui.QLabel('Playlist Name:')
        lblpath = QtGui.QLabel('Path to download:')
        self.sgplaylist = QtGui.QLineEdit(self)
        
        # Shipment ID
        lblShipment = QtGui.QLabel('Shipment ID:')
        self.shipmentId = QtGui.QLineEdit(self)
        
        self.sgplaylist.setCompleter(self.completer)
        self.completer.setModel(self.model)
        
        self.sgpath = QtGui.QLineEdit(self)
        
        # Log Label
        self.lblLog = QtGui.QTextBrowser()
        self.progressBar = QtGui.QProgressBar(self)
        # BETTER WAY TO DO THIS?
        self.userFields = [self.sgurl, self.sgscript, self.sgapikey, self.sgplaylist,
                           self.sgpath, self.lblLog, self.progressBar]
        self.btn = QtGui.QPushButton('Start Download', self)
        self.btn.setToolTip('All the fields must be filled.')
        self.btn.resize(self.btn.sizeHint())
        
        qbtn = QtGui.QPushButton('Quit', self)
        qbtn.clicked.connect(QtCore.QCoreApplication.instance().quit)
        qbtn.resize(qbtn.sizeHint())
        
        # Scene Checkbox
        sceneCB = QtGui.QCheckBox('Organize by ShotgunScene', self)
        sceneCB.stateChanged.connect(self.isSceneOrgChecked)
        
        self.pathGen = QtGui.QPushButton('Generate Shipment Path', self)
        self.pathGen.setToolTip('Get incoming path to the shipment ID given above.')
        #self.pathGen.resize(self.pathGen.sizeHint())
                
        lblLoc = 5
        editLoc = 6
        editSpan = 3
        grid = QtGui.QGridLayout()
        grid.setSpacing(10)
        grid.addWidget(lblUrl, 1, lblLoc)
        grid.addWidget(self.sgurl, 1, editLoc, 1, editSpan)
        
        grid.addWidget(lblScript, 2, lblLoc)
        grid.addWidget(self.sgscript, 2, editLoc, 1, editSpan)
        grid.addWidget(lblApiKey, 3, lblLoc)
        grid.addWidget(self.sgapikey, 3, editLoc, 1, editSpan)
        
        dllblLoc = 0
        dlsgLoc = 1
        grid.addWidget(self.btn, 7, dllblLoc)
        grid.addWidget(self.pathGen, 7, dlsgLoc)
        grid.addWidget(qbtn, 7, 2)
        
        grid.addWidget(sceneCB, 7, 3)
        
        grid.addWidget(lblplaylist, 1, dllblLoc)
        grid.addWidget(self.sgplaylist, 1, dlsgLoc, 1, editSpan)
        grid.addWidget(lblpath, 2, dllblLoc)
        grid.addWidget(self.sgpath, 2, dlsgLoc, 1, editSpan)
        
        grid.addWidget(lblShipment, 3, dllblLoc)
        grid.addWidget(self.shipmentId, 3, dlsgLoc, 1, editSpan)
        
        grid.addWidget(self.lblLog, 5, dllblLoc, 1, 9)
        grid.addWidget(self.progressBar, 6, dllblLoc, 1, 9)
        
        self.setLayout(grid)
        
        self.setGeometry(300, 300, 800, 150)
        self.setWindowTitle('Shotgun Grab')
        self.setWindowIcon(QtGui.QIcon('randh.jpg'))
        self.show()
        
    def isSceneOrgChecked(self, state):
        if state == QtCore.Qt.Checked:
            self.orgByScene = True
        else:
            self.orgByScene = False

    def engageButton(self, value):
        self.btn.setEnabled(value)
    
    def setProgressBarRange(self, value):
        self.progressBar.setRange(0, value)
        
    def updateProgressBar(self, value):
        self.progressBar.setValue(value)
    
    def printLog(self, text):
        self.lblLog.append(text)
        
    def isFieldsFilled(self):
        for field in self.userFields:
            if isinstance(field, QtGui.QLineEdit):
                field.setText(str(field.displayText()))
                if str(field.text()) is "":
                    return False
        return True
    
    def printError(self, errorMessage):
        errorDialog = QtGui.QErrorMessage(self)
        errorDialog.showMessage(errorMessage)
        self.connect(errorDialog, QtCore.SIGNAL("accepted()"), errorDialog.close)
    
    def closeEvent(self, event):
        reply = QtGui.QMessageBox.question(self, 'Message',
                    "Are you sure to quit?", QtGui.QMessageBox.Yes |
                    QtGui.QMessageBox.No)
        
        if reply == QtGui.QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()
            
    @property
    def shotgunURL(self):
        return str(self.sgurl.text())
    
    @shotgunURL.setter
    def shotgunURL(self, value):
        self.sgurl.setText(value)
    
    @property
    def shotgunScript(self):
        return str(self.sgscript.text())
    
    @shotgunScript.setter
    def shotgunScript(self, value):
        self.sgscript.setText(value)        
        
    @property
    def shotgunKey(self):
        return str(self.sgapikey.text())
    
    @shotgunKey.setter
    def shotgunKey(self, value):
        self.sgapikey.setText(value)
        
    @property
    def playlist(self):
        return str(self.sgplaylist.text())
    
    @playlist.setter
    def playlist(self, value):
        self.sgplaylist.setText(value)
        
    @property
    def path(self):
        return str(self.sgpath.text())
    
    @path.setter
    def path(self, value):
        self.sgpath.setText(value)
        
    @property
    def shipment(self):
        return str(self.shipmentId.text())
    
    @shipment.setter
    def shipment(self, value):
        self.shipmentId.setText(value)
        
class GenericThread(QtCore.QThread):
    def __init__(self, function, *args, **kwargs):
        QtCore.QThread.__init__(self)
        self.function = function
        self.args = args
        self.kwargs = kwargs
        
    def __del__(self):
        self.wait()
        
    def run(self):
        return self.function(*self.args, **self.kwargs)
