
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
import commands
import os
import os.path
import sys
import cookielib
import urllib2
from parsedatetime import parsedatetime as dt
from parsedatetime import parsedatetime_consts as dt_consts
from time import mktime
from datetime import datetime
from shotgun_api3 import Shotgun
from shotgun_api3.shotgun import Fault
import re

from urllib2 import urlopen
from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import QThread, QMutex, QMutexLocker, SIGNAL

# R&H imports
import rh.argument
import rh.logutils.options
from rh.prototype.ui.shotgungrab import SGInterface, GenericThread

class RHShotgun(object):
    def __init__(self):
        self.sgi = SGInterface()
        self.sgi.shotgunURL = 'https://warnerbros.shotgunstudio.com'
        self.sgi.shotgunScript = 'rhythm_test_script'
        self.sgi.shotgunKey = '1491d2d5dbd6e9f800e353805013be31b42cba5c'
        # JUST FOR TESTING. REMOVE AFTERWARDS
        self.sgi.playlist = 'Assassinations for R&H'
        self.sgi.path = '/toast/misc/jets/slu/testSG/'
        self.sgi.btn.clicked.connect(self.startDownload)
        self.sgi.pathGen.clicked.connect(self.getShipmentId)
        try:
            sg = self.getShotgun(
                self.sgi.shotgunURL,
                self.sgi.shotgunScript,
                self.sgi.shotgunKey
            )
        except Fault:
            pass
        else:
            # Hardcode BoA's ID Number
            plNames = sg.find('Playlist', [['project', 'is', {'type':'Project', 'id': 64}]], ['code'])
            for name in plNames:
                self.sgi.playlistNames.append(name['code'])
            self.sgi.setModel(self.sgi.model, self.sgi.playlistNames)
    
    def getShipmentId(self):
        if self.sgi.shipment is None:
            self.sgi.printError('Must fill in Shipment Id')
            return
        stageArea = commands.getoutput('jt_mkstagearea {0}'.format(self.sgi.shipment))
        pathMatch = re.search('\/.*\/$', stageArea)
        if pathMatch:
            self.sgi.path = "{0}incoming/".format(pathMatch.group(0))
        else:
            self.sgi.printError('Unable to find the stage area for this shipment ID.')
        
    def startDownload(self):
        if not self.sgi.isFieldsFilled():
            self.sgi.printError('Fill out all the fields')
            return
        
        sg = self.getShotgun(
            self.sgi.shotgunURL,
            self.sgi.shotgunScript,
            self.sgi.shotgunKey
        )
        
        if sg is not None:
            self.shotgunPull(sg, self.sgi.playlist, self.sgi.path, self.sgi)
        
        
    def getShotgun(self, url, script, apikey):
        """ (Shotgun) - Wrapper for creating a shotgun object.  Handles error if
        incorrect information is inputted.
        """
        try:
            sg = Shotgun(url, script, apikey)
        except:
            self.sgi.printError("Error: Please ensure all server information is correct.")
            return
        return sg
    
    def shotgunPull(self, sg, plName, path, qt):
        """ (None) - Takes the given information and attemps to process them in shotgun.
        Resolves any errors that may occur from incorrect fields.  Once playlist, path,
        and sg information are valid, it will thread the information to download the files.
        """
        self.setupDirs(path, qt)
        # Retrieve all the versions from given playlist in shotgun
        plfields = ['id', 'versions']
        playlist = None
        while playlist is None:
            plfilters = [['code', 'is', plName]]
            try:
                playlist = sg.find_one('Playlist', plfilters, plfields)
            except Fault as e:
                self.sgi.printError("Error: {0}".format(e))
                return
            if playlist is None:
                self.sgi.printError("{0} is not a valid Playlist. Enter a valid playlist: ".format(plName))
                return
        plVersions = playlist['versions']
        
        timesince = self.convertTime('1 year ago')
        qt.printLog("Retrieving info from Shotgun...")
        self.thread = WorkerThread()
        self.thread.initialize(sg, plVersions, path, "type", timesince, self.sgi.orgByScene)
        self.sgi.connect(self.thread, SIGNAL("setProgressBarRange(int)"), self.sgi.setProgressBarRange)
        self.sgi.connect(self.thread, SIGNAL("updateProgressBar(int)"), self.sgi.updateProgressBar)
        self.sgi.connect(self.thread, SIGNAL("updateLog(QString)"), self.sgi.printLog)
        self.sgi.connect(self.thread, SIGNAL("engageButton(bool)"), self.sgi.engageButton)
        self.thread.start()

    
    def convertTime(self, time):
        """ (Datetime) Takes a string and parses the contents to a Datetime
        object.  If the current time input is not valid, it will return a
        minimum datetime object.
        """    
        # Get a datetime object of users date if required.
        tparser = dt.Calendar(dt_consts.Constants())
        
        # If user specifies a time, make all the necessary conversions to datetime
        (timesince, _) = tparser.parse(time)
        timesince = datetime.fromtimestamp(mktime(timesince))
        return timesince
        
    def setupDirs(self, path, qt):
        """ (None) Checks if the path given exists.  If it doesn't exist,
        inform that path is non existent and create the path.
        """
        if not os.path.exists(path):
            qt.printLog("Path {path} does not exist.  Creating...".format(path=path),)
            os.makedirs(path)
            qt.printLog("Complete")
            
    def downloadFromShotgunWeblink(self, url):
        """ (File) Opens the url and reads in the data into an object.
        This object can be written to a file for output.
        """
        from shotgun_api3.shotgun import ShotgunError
        try:
            request = urllib2.Request(url)
            request.add_header('User-agent',
                               "Mozilla/5.0 (X11; Linux i686 on x86_64; "\
                               "rv:13.0) Gecko/20100101 Firefox/13.0.1")
            attachment = urllib2.urlopen(request).read()
    
        except IOError, e:
            err = "Failed to open %s" % url
            if hasattr(e, 'code'):
                err += "\nWe failed with error code - %s." % e.code
            elif hasattr(e, 'reason'):
                err += "\nThe error object has the following 'reason' "\
                    "attribute :", e.reason
                err += "\nThis usually means the server doesn't exist, is "\
                    "down, or we don't have an internet connection."
            raise ShotgunError(err)
        else:
            if attachment.lstrip().startswith('<!DOCTYPE '):
                error_string = "\n%s\nThe server generated an error trying "\
                    "to download the Attachment. \nURL: %s\n"\
                    "Either the file doesn't exist, or it is a local file "\
                    "which isn't downloadable.\n%s\n" % ("="*30, url, "="*30)
                raise ShotgunError(error_string)
        return attachment
    
    def downloadFiles(self, sg, attachmentIds, filetype, time, qt):
        """ (None) Uses the shotgun object to download all files in attachmentIds.
        filetype will only download files of that type.  Time will avoid downloading
        items older than specified.  
        """
        itemLength = len(attachmentIds.keys())
        currentVal = 0
        qt.progressBar.setRange(currentVal, itemLength)
        for attachId, (attachName, attachDate) in attachmentIds.iteritems():
            currentVal = currentVal + 1
            qt.progressBar.setValue(currentVal)
            qt.printLog("Downloading {val}/{length} {name}...".format(val= currentVal,
                                                                length=itemLength,
                                                                name=attachName),)
            if attachDate < time:
                qt.printLog("Skipping: File older than specified")
                continue
            from shotgun_api3.shotgun import ShotgunError
            
            # Handles cases which the source file is a web link
            if 'http' in attachId:
                url = attachId
                sid = sg._get_session_token()
                cj = cookielib.LWPCookieJar()
                c = cookielib.Cookie('0', '_session_id', sid, None, False,
                    sg.config.server, False, False, "/", True, False, None, True,
                    None, None, {})
                cj.set_cookie(c)
                cookie_handler = urllib2.HTTPCookieProcessor(cj)
                urllib2.install_opener(urllib2.build_opener(cookie_handler))
                attachFile = self.downloadFromShotgunWeblink(url)
            else:
                try:
                    attachFile = sg.download_attachment(attachId)
                except ShotgunError as e:
                    qt.printLog("Error Downloading file: {error}".format(error=e))
                    continue
            with open(attachName, 'w') as wfile:
                wfile.write(attachFile)
            qt.printLog("Complete")
            
    def accumFileInfo(self, sg, versions, path):
        """ (Dict) Returns a dictionary with a {ID : (filename, dateUpdated)}
        structure.  Runs through the shotgun server and pulls data from each
        'Version'.
        """
        attachmentIds = {}
        filenames = []
        verfields = ['id', 'sg_uploaded_movie', 'sg_source_file', 'updated_at', 'code']
        filefields = ('sg_uploaded_movie', 'sg_source_file')
        for version in versions:
            # Get the version that matches the ID
            verfilter = [['id', 'is', version['id']]]
            curFile = sg.find_one('Version', verfilter, verfields)
            for filefield in filefields:
                try:
                    curURL = curFile[filefield]['url']
                except TypeError:
                    continue
                curName = curFile[filefield]['name']
                try:
                    urlopen(curName)
                except ValueError:
                    pass
                else:
                    # TODO: Get the right file from link
                    curID = curName
                    curName = curFile['code']
                    curDate = curFile['updated_at'].replace(tzinfo=None)
                    filename = "{path}/{file}".format(path=path, file=curName)
                    attachmentIds[curID] = (filename, curDate)
                    continue
                
                curDate = curFile['updated_at'].replace(tzinfo=None)
                # curName is not always the item name, it may be a url.
                filename = "{path}/{file}".format(path=path, file=curName)
                if filename in filenames:
                    continue
                else:
                    filenames.append(filename)
                (_, ext) = os.path.splitext(filename)
                curID = curURL.split('/')[-1]
                attachmentIds[curID] = (filename, curDate)
        return attachmentIds
    
class WorkerThread(QThread):
    def __init__(self, parent=None):
        QThread.__init__(self, parent)
        self.exiting = False
        self.n = 1
        self.completed = False
        self.stopped = False
        self.mutex = QMutex()
        
    def initialize(self, sg, versions, path, filetype, time, orgByScene):
        self.sg = sg
        self.filetype = filetype
        self.time = time
        self.versions = versions
        self.path = path
        self.orgByScene = orgByScene
        
    def __del__(self):
        self.exiting = True
        self.stop()
        
    
    def stop(self):
        with QMutexLocker(self.mutex):
            self.stopped = True
       
    def isStopped(self):
        with QMutexLocker(self.mutex):
            return self.stopped
        
    def run(self):
        self.emit(SIGNAL("engageButton(bool)"), False)
        attachmentIds = self.accumFileInfo(self.sg, self.versions, self.path, self.orgByScene)
        self.emit(SIGNAL("setProgressBarRange(int)"), len(attachmentIds))
        self.downloadFiles(self.sg, attachmentIds, self.filetype, self.time)
        self.emit(SIGNAL("engageButton(bool)"), True)
        self.quit()
        
    def accumFileInfo(self, sg, versions, path, orgByScene):
        """ (Dict) Returns a dictionary with a {ID : (filename, dateUpdated)}
        structure.  Runs through the shotgun server and pulls data from each
        'Version'.
        """
        attachmentIds = {}
        filenames = []
        verfields = ['id', 'sg_uploaded_movie', 'sg_source_file', 'updated_at', 'code', 'sg_scenes']
        filefields = ('sg_uploaded_movie', 'sg_source_file')
        scenes = []
        for version in versions:
            # Get the version that matches the ID
            verfilter = [['id', 'is', version['id']]]
            curFile = sg.find_one('Version', verfilter, verfields)
            if orgByScene:
                scenes = [scene['name'] for scene in curFile['sg_scenes']]
            # Create scene folders
            for scene in scenes:
                if not os.path.exists(os.path.join(path, scene)):
                    os.mkdir(os.path.join(path, scene))
            for filefield in filefields:
                try:
                    curURL = curFile[filefield]['url']
                except TypeError:
                    continue
                curName = curFile[filefield]['name']
                try:
                    urlopen(curName)
                except ValueError:
                    pass
                else:
                    # TODO: Get the right file from link
                    curID = curName
                    curName = curFile['code']
                    curDate = curFile['updated_at'].replace(tzinfo=None)
                    filename = "{path}/{file}".format(path=path, file=curName)
                    attachmentIds[curID] = (filename, curDate)
                    continue
                
                curDate = curFile['updated_at'].replace(tzinfo=None)
                # curName is not always the item name, it may be a url.
                filename = "{path}/{file}".format(path=path, file=curName)
                if filename in filenames:
                    continue
                else:
                    filenames.append(filename)
                (_, ext) = os.path.splitext(filename)
                curID = curURL.split('/')[-1]
                attachmentIds[curID] = (filename, curDate, scenes)
        return attachmentIds
        
    def downloadFiles(self, sg, attachmentIds, filetype, time):
        """ (None) Uses the shotgun object to download all files in attachmentIds.
        filetype will only download files of that type.  Time will avoid downloading
        items older than specified.  
        """
        while not self.exiting and self.n > 0:
            itemLength = len(attachmentIds.keys())
            currentVal = 0
            for attachId, (attachName, attachDate, scenes) in attachmentIds.iteritems():
                currentVal = currentVal + 1
                self.emit(SIGNAL("updateProgressBar(int)"), currentVal)

                if attachDate < time:
                    logString = "Skipping: File older than specified"
                    self.emit(SIGNAL("updateLog(QString)"), logString)
                    continue
                from shotgun_api3.shotgun import ShotgunError
                
                # Handles cases which the source file is a web link
                if 'http' in attachId:
                    url = attachId
                    sid = sg._get_session_token()
                    cj = cookielib.LWPCookieJar()
                    c = cookielib.Cookie('0', '_session_id', sid, None, False,
                        sg.config.server, False, False, "/", True, False, None, True,
                        None, None, {})
                    cj.set_cookie(c)
                    cookie_handler = urllib2.HTTPCookieProcessor(cj)
                    urllib2.install_opener(urllib2.build_opener(cookie_handler))
                    attachFile = self.downloadFromShotgunWeblink(url)
                else:
                    try:
                        attachFile = sg.download_attachment(attachId)
                    except ShotgunError as e:
                        logString = "Error downloading file: {error}".format(error=e)
                        self.emit(SIGNAL("updateLog(QString)"), logString)
                        continue
                    
                # Handles if we want to organize by the shotgun scene
                dirname = os.path.dirname(attachName)
                filename = os.path.basename(attachName)
                if len(scenes) > 0:
                    scene = scenes.pop(0)
                    with open(os.path.join(dirname, scene, filename), 'w') as wfile:
                        logString =  "Downloading {val}/{length} {name}...".format(
                        val= currentVal,
                        length=itemLength,
                        name=os.path.join(dirname, scene, filename)
                        )
                        self.emit(SIGNAL("updateLog(QString)"), logString)
                        wfile.write(attachFile)
                    self.emit(SIGNAL("updateLog(QString)"), "Complete")
                    for curscene in scenes:
                        logString =  "Creating symlink for {0}".format(
                            os.path.join(dirname, curscene, filename)
                        )
                        self.emit(SIGNAL("updateLog(QString)"), logString)
                        os.symlink(os.path.join(dirname, scene, filename), os.path.join(dirname, curscene, filename))
                else:    
                    with open(attachName, 'w') as wfile:
                        logString = "Downloading {val}/{length} {name}...".format(
                            val= currentVal,
                            length=itemLength,
                            name=attachName
                        )
                        self.emit(SIGNAL("updateLog(QString)"), logString)
                        wfile.write(attachFile)
                    self.emit(SIGNAL("updateLog(QString)"), "Complete")
                self.exiting = True
                self.n = 0
        
    def downloadFromShotgunWeblink(self, url):
        """ (File) Opens the url and reads in the data into an object.
        This object can be written to a file for output.
        """
        from shotgun_api3.shotgun import ShotgunError
        
        try:
            request = urllib2.Request(url)
            request.add_header('User-agent',
                               "Mozilla/5.0 (X11; Linux i686 on x86_64; "\
                               "rv:13.0) Gecko/20100101 Firefox/13.0.1")
            attachment = urllib2.urlopen(request).read()
    
        except IOError, e:
            err = "Failed to open %s" % url
            if hasattr(e, 'code'):
                err += "\nWe failed with error code - %s." % e.code
            elif hasattr(e, 'reason'):
                err += "\nThe error object has the following 'reason' "\
                    "attribute :", e.reason
                err += "\nThis usually means the server doesn't exist, is "\
                    "down, or we don't have an internet connection."
            raise ShotgunError(err)
        else:
            if attachment.lstrip().startswith('<!DOCTYPE '):
                error_string = "\n%s\nThe server generated an error trying "\
                    "to download the Attachment. \nURL: %s\n"\
                    "Either the file doesn't exist, or it is a local file "\
                    "which isn't downloadable.\n%s\n" % ("="*30, url, "="*30)
                raise ShotgunError(error_string)
        return attachment 