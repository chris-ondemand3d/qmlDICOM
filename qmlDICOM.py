# This Python file uses the following encoding: utf-8
import os, sys, urllib.request, json, time, traceback
from PySide2.QtGui import QGuiApplication
from PySide2.QtQml import QQmlApplicationEngine, qmlRegisterType
from PySide2.QtQuick import QQuickView
from PySide2.QtCore import Qt, QObject, QFileInfo, QAbstractTableModel, QModelIndex, QDir, QUrl, qDebug, Signal, Slot, QRunnable, QThreadPool, Property
from PySide2.QtSql import QSqlDatabase, QSqlQueryModel, QSqlQuery
from PySide2.QtWidgets import QFileSystemModel
from enum import Enum
import copy
import gdcm


# Todo on Nov. 22
# 1) Implement studySeriesModel - OK
# 2) Open method
# 3) Open Image Window
# 4) Laplace Histogram
# 5) Orca Library integration
# 6) Rendering - multiobject rendering
# 7) Modular structure


class myStudyModel(QAbstractTableModel):
    COLUMN_NAMES = ("patientID", "patientName", "patientDOB", "patientSex", "studyID", "studyInstanceUID", "studyDateTime", "studyDesription", "numberOfSeries")

    selectRow = Signal(str)

    def __init__(self):
        QAbstractTableModel.__init__(self)
        self.rows = []

    def rowCount(self, parent):
        return len(self.rows)

    def columnCount(self, parent):
        return len(self.COLUMN_NAMES)

    def roleNames(self):
        roles = {}
        for i, header in enumerate(self.COLUMN_NAMES):
            roles[int(Qt.UserRole)+i+1]=header.encode()
        return roles

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole:
            column = self.COLUMN_NAMES[section]
        else:
            column = None
        return column

    def data(self, index, role=Qt.DisplayRole):
        row = index.row()
        if (role <= Qt.UserRole):
            value = self.rows[row][index.column()]
        else:
            columnIdx = int(role) - int(Qt.UserRole) - 1
            #modelIndex = self.index(index.row(), columnIdx)
            #value = QAbstractTableModel.data(self,modelIndex,Qt.DisplayRole)
            value = self.rows[row][columnIdx]
        return value


    @Slot(object)
    def refreshStudyList(self, studyList):
        print("Refresh StudyList:",len(self.rows),len(studyList))
        #Remove current Rows
        if (len(self.rows)>0):
            self.beginRemoveRows(QModelIndex(),0,len(self.rows))
            self.rows = []
            self.endRemoveRows()
        #Insert all Rows in studyList
        if (len(studyList)>0):
            self.beginInsertRows(QModelIndex(),0,len(studyList)-1)
            for row in studyList:
                self.rows.append(row)
            self.endInsertRows()
        #print(self.rows)

    @Slot(int)
    def notifyStudyUID(self,row):
        value = self.rows[row][5]
        #print(value)
        self.selectRow.emit(value)


class studySeriesModel(QAbstractTableModel):
    COLUMN_NAMES = ("studyID", "studyInstanceUID", "seriesNum", "seriesInstanceUID", "sopClassUID", "sopInstanceUID", "numberOfImages")

    def __init__(self):
        QAbstractTableModel.__init__(self)
        self.rows = []
        self.allrows = []

    def rowCount(self, parent):
        return len(self.rows)

    def columnCount(self, parent):
        return len(self.COLUMN_NAMES)

    def roleNames(self):
        roles = {}
        for i, header in enumerate(self.COLUMN_NAMES):
            roles[int(Qt.UserRole)+i+1]=header.encode()
        return roles

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole:
            column = self.COLUMN_NAMES[section]
        else:
            column = None
        return column

    def data(self, index, role=Qt.DisplayRole):
        row = index.row()
        if (role <= Qt.UserRole):
            value = self.rows[row][index.column()]
        else:
            columnIdx = int(role) - int(Qt.UserRole) - 1
            value = self.rows[row][columnIdx]
        return value

    @Slot(object)
    def refreshSeriesList(self, seriesList):
        print("Refresh SeriesList:",len(self.allrows),len(seriesList))
        self.allrows = seriesList

    @Slot(str)
    def refreshUID(self, studyUID):
        #Remove current Rows
        if (len(self.rows)>0):
            self.beginRemoveRows(QModelIndex(),0,len(self.rows))
            self.rows = []
            self.endRemoveRows()
        #Insert all Rows in studyList
        if (len(self.allrows)>0):
            cnt = 0
            for row in self.allrows:
                if (row[1] == studyUID): cnt += 1
            self.beginInsertRows(QModelIndex(),0,cnt-1)
            for row in self.allrows:
                if (row[1] == studyUID):
                    self.rows.append(row)
            self.endInsertRows()

class ProgressWatcher(gdcm.SimpleSubjectWatcher, QObject):
    notifyProgress = Signal(float)

    def __init__(self,s,cc):
        QObject.__init__(self)
        gdcm.SimpleSubjectWatcher.__init__(self,s,cc)
        self._progress = 0.0

    def readProgress(self):
        return self._progress

    def progressChanged(self):
        print("Progress changed to ",self._progress)

    progress = Property(float, readProgress, notify=progressChanged)

    def ShowProgress(self, sender, event):
        pe = gdcm.ProgressEvent.Cast(event)
        val = float(pe.GetProgress())
        if ( (val - self._progress) > 0.1 or (self._progress - val) > 0.1):
            self._progress = val
            #print(self._progress)
            self.notifyProgress.emit(self._progress)

    def StartFilter(self):
        pass
    def EndFilter(self):
        pass
    def ShowFileName(self, sender, event):
        pass


class WorkerSignal(QObject):
    finished = Signal()
    error = Signal(tuple)
    result = Signal(object)

class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignal()
        # Add the callback to our kwargs
        #self.kwargs['progress_callback'] = self.signals.progress

    @Slot()
    def run(self):
        '''
        Initialise the runner function with passed args, kwargs.
        '''
        # Retrieve args/kwargs here; and fire processing using them
        try:
            res = self.fn(*self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(res) # Return the result of the processing
        finally:
            self.signals.finished.emit() # Done



class myDirModel(QFileSystemModel,QObject):

    dirSelected = Signal(QModelIndex)
    scanProgressed = Signal(float)
    scanDirStudy = Signal(object)
    scanDirSeries = Signal(object)

    def __init__(self):
        QFileSystemModel.__init__(self)
        self.sizeRole = int(Qt.UserRole+1)
        self.dirSelected.connect(self.selDirPath)
        self.Scanning = False
        self.threadpool = QThreadPool()
        self.progress = 0.0
        print("Multithreading with maximum %d threads" % self.threadpool.maxThreadCount())

    def sizeString(self, fInfo):
        if (not fInfo.isDir()):
           return ""
        dir = QDir(fInfo.filePath())
        fileFilters = QDir.Filters(QDir.Files|QDir.System|QDir.Hidden)
        size = 0
        for filePath in dir.entryList(fileFilters):
            fi = QFileInfo(dir,filePath)
            size += fi.size()

        if (size > 1024 * 1024 * 10):
            return str("%4.1f" % (size / (1024 * 1024))) + 'MB'
        if (size > 1024 * 10):
            return str("%4.1f" % (size / 1024)) + 'KB'
        return str(size)

    def data(self, index, role=Qt.DisplayRole):
        if (index.isValid() and role == self.sizeRole):
            return self.sizeString(self.fileInfo(index))
        else:
            return QFileSystemModel.data(self,index,role)

    def roleNames(self):
        roles = QFileSystemModel.roleNames(self);
        header = "size"
        roles[int(self.sizeRole)]=header.encode()
        return roles


    @Slot(object)
    def scanDir_output(self, res):
        qDebug("Return with result(study): "+res[0].__str__())
        qDebug("Return with result(series): "+res[1].__str__())

        self.scanProgressed.emit(1.0)
        self.scanDirStudy.emit(res[0])
        self.scanDirSeries.emit(res[1])
        self.Scanning = False

    @Slot()
    def thread_complete(self):
        qDebug("Thread Complete")
        self.Scanning = False

    @Slot()
    def scanProgress(self):
        self.progress = self.w.progress
        # qDebug("Progress callback " + str(self.w.progress))
        self.scanProgressed.emit(self.w.progress)


    @Slot(QModelIndex)
    def selDirPath(self,index):
        fInfo = self.fileInfo(index)
        qDebug("Scanning "+fInfo.filePath())

        # instantiate Scanner:
        self.sp = gdcm.Scanner.New();
        s = self.sp.__ref__()
        self.w = ProgressWatcher(s, 'Watcher')
        self.w.notifyProgress.connect(self.scanProgress)

        # Populate Study, Series, Image lists
        if (not self.Scanning):
            pass # start scanning
            self.Scanning = True
            worker = Worker(self.scanDir, fInfo.filePath(), s) # Any other args, kwargs are passed to the run function
            worker.signals.result.connect(self.scanDir_output)
            worker.signals.finished.connect(self.thread_complete)
            # Execute
            self.threadpool.start(worker)
            # Test how many thread starts?


    def scanDir(self, strPath, s):
        d = gdcm.Directory();
        nfiles = d.Load(strPath);
        if (nfiles == 0): sys.exit(-1); # No DICOM files in the directory

        filenames = d.GetFilenames()
        qDebug("The number of files to scan is "+ str(len(filenames)))

        # Define the set of tags we are interested in, may need more
        t1 = gdcm.Tag(0x10, 0x20);  # Patient ID
        t2 = gdcm.Tag(0x10, 0x10);  # Patient Name
        t3 = gdcm.Tag(0x20, 0x10);  # Study ID
        t4 = gdcm.Tag(0x20, 0x0d);  # Study Instance UID
        t5 = gdcm.Tag(0x20, 0x0e);  # Series Instance UID
        t6 = gdcm.Tag(0x20, 0x11);  # Series Number
        t7 = gdcm.Tag(0x28, 0x08);  # Number of Frames
        t8 = gdcm.Tag(0x20, 0x32);  # Image Position
        t10 = gdcm.Tag(0x28, 0x30);  # Pixel Spacing
        t11 = gdcm.Tag(0x20, 0x37);  # Image Orientation Patient
        t12 = gdcm.Tag(0x28, 0x02);  # Samples per pixel
        t13 = gdcm.Tag(0x28, 0x04);  # Photometric Interpretation
        t14 = gdcm.Tag(0x28, 0x10);  # Rows
        t15 = gdcm.Tag(0x28, 0x11);  # Column
        t16 = gdcm.Tag(0x28, 0x101);  # BitStored
        t17 = gdcm.Tag(0x02, 0x02);  # Media Storage SOP Class UID
        t18 = gdcm.Tag(0x02, 0x03);  # Media Storage SOP Instance UID
        t19 = gdcm.Tag(0x02, 0x10);  # Transfer Syntax
        t20 = gdcm.Tag(0x08, 0x16);  # SOP Class UID
        t21 = gdcm.Tag(0x08, 0x18);  # SOP Instance UID
        t22 = gdcm.Tag(0x5200, 0x9229);  # Shared functional group
        t23 = gdcm.Tag(0x5200, 0x9230);  # Per frame functional group
        t24 = gdcm.Tag(0x0028, 0x1050);  # WindowCenter
        t25 = gdcm.Tag(0x0028, 0x1051);  # WindowWidth
        t26 = gdcm.Tag(0x0028, 0x1052);  # Rescale Intercept
        t27 = gdcm.Tag(0x0028, 0x1053);  # Rescale Slope
        t28 = gdcm.Tag(0x0028, 0x1054);  # Rescale Type
        t29 = gdcm.Tag(0x0010, 0x0030); # PatientBirthDate
        t30 = gdcm.Tag(0x0010, 0x0040); # PatientSex
        t31 = gdcm.Tag(0x0008, 0x0020); # Study Date
        t32 = gdcm.Tag(0x0008, 0x1030); # Study Description


        s.AddTag(t1);
        s.AddTag(t2);
        s.AddTag(t3);
        s.AddTag(t4);
        s.AddTag(t5);
        s.AddTag(t6);
        s.AddTag(t7);
        s.AddTag(t8);
        s.AddTag(t10);
        s.AddTag(t11);
        s.AddTag(t12);
        s.AddTag(t13);
        s.AddTag(t14);
        s.AddTag(t15);
        s.AddTag(t16);
        s.AddTag(t17);
        s.AddTag(t18);
        s.AddTag(t19);
        s.AddTag(t20);
        s.AddTag(t21);
        s.AddTag(t22);
        s.AddTag(t23);
        s.AddTag(t29);
        s.AddTag(t30);
        s.AddTag(t31);
        s.AddTag(t32);

        b = s.Scan(filenames);

        # if no files in this directory
        dicomfiles = []
        if (not b):
            qDebug("Empty directory")
            return dicomfiles

        study_list = []
        series_list = []
        series_count = {}
        image_count = {}

        for aFile in filenames:
            if (s.IsKey(aFile)):  # existing DICOM file
                # qDebug("Scan "+aFile)
                is_multiframe = 0

                pttv = gdcm.PythonTagToValue(s.GetMapping(aFile))
                pttv.Start()
                patient_DOB = ""
                patient_sex = ""
                study_description = ""

                # iterate until the end:
                while (not pttv.IsAtEnd()):



                    # get current value for tag and associated value:
                    # if tag was not found, then it was simply not added to the internal std::map
                    # Warning value can be None
                    tag = pttv.GetCurrentTag()
                    value = pttv.GetCurrentValue()

                    if (tag == t1):
                        #print ("PatientID->",value)
                        patient_id = value
                    elif (tag == t2):
                        #print ("PatientName->",value)
                        patient_name = value
                    elif (tag == t29):
                        # print ("PatientBirthDate->",value)
                        patient_DOB = value
                    elif (tag == t30):
                        patient_sex = value
                    elif (tag == t3):
                        # print ("StudyID->",value)
                        study_id = value
                    elif (tag == t4):
                        studyinstance_uid = value
                    elif (tag == t31):
                        # print ("StudyDate->",value)
                        study_date = value
                    elif (tag == t32):
                        study_description = value
                    elif (tag == t6):
                        series_num = value
                        # print ("SeriesNum->",value)
                    elif (tag == t5):
                        # print ("SeriesInstanceUID->",value)
                        seriesinstance_uid = value
                    elif (tag == t7):
                        # print ("NumberOfFrame->",value)
                        if (int(value) > 1):
                            is_multiframe = int(value)
                        else:
                            is_multiframe = 0
                    elif (tag == t19):
                        # print("Transfer Syntax->",value)
                        pass
                    elif (tag == t20):
                        # print("SOP Class UID->",value)
                        sopclass_uid = value
                        #sop_ClassName = sopclass_uid.GetName()
                    elif (tag == t21):
                        # print("SOP Instance UID->",value)
                        sopinstance_uid = value
                    # increment iterator
                    pttv.Next()

                # new StudyInstanceUID
                if (studyinstance_uid not in series_count.keys()):
                    # Add to the study_list
                    study_list.append([patient_id, patient_name, patient_DOB, patient_sex, study_id, studyinstance_uid, study_date, study_description, 0])
                    # Add count
                    series_count[studyinstance_uid] = 0

                # new SeriesInstanceUID
                if (seriesinstance_uid not in image_count.keys()):
                    # Add to the series_list
                    series_list.append([study_id, studyinstance_uid, seriesinstance_uid, series_num, sopclass_uid, sopinstance_uid, 0])
                    # Add count
                    image_count[seriesinstance_uid] = 0
                    series_count[studyinstance_uid] += 1

                if (is_multiframe==0):
                    image_count[seriesinstance_uid] += 1
                else:
                    image_count[seriesinstance_uid] += is_multiframe

        # print(series_count)
        # print(image_count)

        # for each study_list items update series_count from series_count(studyinstance_uid)
        for study in study_list:
            study[8] = series_count[study[5]]

        # for each series_list items update images_count from image_count(seriesinstance_uid)
        for series in series_list:
            series[6] = image_count[series[2]]

        #print(study_list)
        #print(series_list)

        return study_list, series_list



if __name__ == "__main__":

    #Set up the application window
    app = QGuiApplication(sys.argv)

    #Expose the list to the Qml code
    m_Database = QSqlDatabase()
    m_Database = QSqlDatabase.addDatabase("QSQLITE");
    m_Database.setDatabaseName("C:\dev\Work\python\SQLTest\o3.db");

    # Don't know why it is not working with (.mde file?, ...)
    #    m_Database = QSqlDatabase.addDatabase("QODBC");
    #    m_Database.setDatabaseName("DRIVER={Microsoft Access Driver (*.mdb)}; FIL={MS Access}; DBQ=C:\\OnDemand3DApp\\Users\\Common\\MasterDB\\lucion.mde;")

    if (not m_Database.open()):
        qDebug("ERROR")
    else:
        qDebug("DB Opened")

    my_StudyModel = myStudyModel()
    my_SeriesModel = studySeriesModel()
    my_StudyModel.selectRow.connect(my_SeriesModel.refreshUID)
    # Temporarily, setting default path manually
    path = "C:\\dev\\Work\\TestData"

    dirModel = myDirModel()
    dirModel.setFilter(QDir.NoDotAndDotDot | QDir.AllDirs)
    dirModel.setRootPath(path)

    #Load the QML file
    qml_file = os.path.join(os.path.dirname(__file__),"main.qml")
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("dirModel",dirModel)
    engine.rootContext().setContextProperty("myStudyModel",my_StudyModel)
    engine.rootContext().setContextProperty("studySeriesModel",my_SeriesModel)
    engine.rootContext().setContextProperty("rootPathIndex", dirModel.index(dirModel.rootPath()))
    engine.load(QUrl.fromLocalFile(os.path.abspath(qml_file)))

    dirModel.scanDirStudy.connect(my_StudyModel.refreshStudyList)
    dirModel.scanDirSeries.connect(my_SeriesModel.refreshSeriesList)

    #Show the window
    if not engine.rootObjects():
        sys.exit(-1)
    sys.exit(app.exec_())
