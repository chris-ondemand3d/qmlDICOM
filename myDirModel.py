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
import pydicom
import numpy
import shutil

# imports for SQL data part
import pyodbc
from datetime import datetime, timedelta
import pandas as pd

# import vtk
from matplotlib import pyplot
from operator import itemgetter, attrgetter
import gdcm


def get_gdcm_to_numpy_typemap():
    """Returns the GDCM Pixel Format to numpy array type mapping."""
    _gdcm_np = {gdcm.PixelFormat.UINT8: numpy.uint8,
                gdcm.PixelFormat.INT8: numpy.int8,
                # gdcm.PixelFormat.UINT12 :numpy.uint12,
                # gdcm.PixelFormat.INT12  :numpy.int12,
                gdcm.PixelFormat.UINT16: numpy.uint16,
                gdcm.PixelFormat.INT16: numpy.int16,
                gdcm.PixelFormat.UINT32: numpy.uint32,
                gdcm.PixelFormat.INT32: numpy.int32,
                # gdcm.PixelFormat.FLOAT16:numpy.float16,
                gdcm.PixelFormat.FLOAT32: numpy.float32,
                gdcm.PixelFormat.FLOAT64: numpy.float64}
    return _gdcm_np


def get_numpy_array_type(gdcm_pixel_format):
    """Returns a numpy array typecode given a GDCM Pixel Format."""
    return get_gdcm_to_numpy_typemap()[gdcm_pixel_format]


def gdcm_to_numpy(image):
    """Converts a GDCM image to a numpy array.
    """
    pf = image.GetPixelFormat()

    assert pf.GetScalarType() in get_gdcm_to_numpy_typemap().keys(), "Unsupported array type %s" % pf
    assert pf.GetSamplesPerPixel() == 1, "SamplesPerPixel is not 1" % pf.GetSamplesPerPixel()
    shape = image.GetDimension(0) * image.GetDimension(1)
    if image.GetNumberOfDimensions() == 3:
        shape = shape * image.GetDimension(2)

    dtype = get_numpy_array_type(pf.GetScalarType())
    gdcm_array = image.GetBuffer().encode("utf-8", errors="surrogateescape")
    volume = numpy.frombuffer(gdcm_array, dtype=dtype)

    if image.GetNumberOfDimensions() == 2:
        result = volume.reshape(image.GetDimension(0), image.GetDimension(1))
    elif image.GetNumberOfDimensions() == 3:
        result = volume.reshape(image.GetDimension(2), image.GetDimension(0), image.GetDimension(1))

    #    result.shape = shape
    return result

def getVector(strIP):
    str = ""
    j1 = 0
    j2 = 0
    for j in range(len(strIP)):
        if (strIP[j] == '\\' and j1 == 0):
            j1 = j
        elif (strIP[j] == '\\' and j1 != 0):
            j2 = j
    x = float(strIP[0:j1])
    y = float(strIP[j1 + 1:j2])
    z = float(strIP[j2 + 1:])
    return x, y, z

def getCosine(strIP):
    i=0
    j=[0,0,0,0,0,0]
    print(strIP)
    for k in range(len(strIP)):
        if (strIP[k]=='\\' and j[i] == 0):
            j[i]=k
            i=i+1
    if (i!=5):
        print("False cosine string")
        return( [1.0, 0.0, 0.0, 0.0, 1.0, 0.0] )
    else:
        print(j)    
        c0 = float(strIP[0:j[0]])
        c1 = float(strIP[j[0]+1:j[1]])
        c2 = float(strIP[j[1]+1:j[2]])
        c3 = float(strIP[j[2]+1:j[3]])
        c4 = float(strIP[j[3]+1:j[4]])
        c5 = float(strIP[j[4]+1:j[5]])
        c6 = float(strIP[j[5]:])
        return( [c0,c1,c2,c3,c4,c5,c6] )

def thru_plane_position(px,py,pz,orientation):
    #position = image.GetOrigin()
    position = (px,py,pz)
    rowvec, colvec = orientation[:3],orientation[3:]
    normal_vec = numpy.cross(rowvec,colvec)
    slice_pos = numpy.dot(position,normal_vec)
    # print(position,rowvec,colvec,normal_vec,slice_pos)
    return slice_pos


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
    # rows
    # allrows
    # imageFiles

    selectRow = Signal(str)

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

    @Slot(object,object)
    def refreshSeriesList(self, seriesList, files):
        print("Refresh SeriesList:",len(self.allrows),len(seriesList))
        self.allrows = seriesList
        self.imageFiles = files

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

    @Slot(int)
    def notifySeriesInstanceUID(self,row):
        # value = Selected SeriesInstanceUID 
        value = self.rows[row][3]        
        self.selectRow.emit(value)

        # Load Data/Rendering Data
        dcmfiles = []

        if len(self.imageFiles[value])==1 :
            if (self.imageFiles[value][0][0] > 1) : # Multiframe, gdcm read to numpy
                qDebug("Multiframe Image")
                reader = gdcm.ImageReader()
                reader.SetFileName(self.imageFiles[value][0][1])
                if (not reader.Read()):
                    qDebug("Cannot read image", self.imageFiles[value][0][1])
                else:
                    image = reader.GetImage()
                    npVolume = numpy.flip(gdcm_to_numpy(image),1)
                    w, d, h = image.GetDimension(0), image.GetDimension(1), image.GetDimension(2)
                    spacing = image.GetSpacing()
                    dx, dy, dz = abs(spacing[0]), abs(spacing[1]), abs(spacing[2])
                    iRescaleIntercept = image.GetIntercept()
                    iRescaleSlope = image.GetSlope()

                    # pyplot single slice
                    x = numpy.arange(0.0, (w+1)*dx, dx)
                    y = numpy.arange(0.0, (d+1)*dy, dy)
                    z = numpy.arange(0.0, (h+1)*dz, dz)
                    pyplot.figure(dpi=200)
                    pyplot.axes().set_aspect('equal', 'datalim')
                    pyplot.set_cmap(pyplot.gray())
                    pyplot.pcolormesh(x, y, npVolume[25,:, :])
                    pyplot.show()

            else:
                qDebug("Single Image Series: Do nothing")
        else:
            qDebug("Multiple slice dicom files")

            ireader = gdcm.ImageReader()
            firstFile = self.imageFiles[value]
            ireader.SetFileName(firstFile[0][1])
            # print("First file is ", firstFile[0][1])
            if (not ireader.Read()):
                print("Cannot read image", firstFile[0][1])
                sys.exit(1)

            image = ireader.GetImage()
            w, d = image.GetDimension(0), image.GetDimension(1)
            cosine = image.GetDirectionCosines()

            pf = image.GetPixelFormat()
            assert pf.GetScalarType() in get_gdcm_to_numpy_typemap().keys(), "Unsupported array type %s" % pf
            assert pf.GetSamplesPerPixel() == 1, "Support only one samples"

            spacing = image.GetSpacing()
            dx = float(spacing[0])
            dy = float(spacing[1])

            iRescaleIntercept = image.GetIntercept()
            iRescaleSlope = image.GetSlope()

            dtype = get_numpy_array_type(pf.GetScalarType())

            print(w,d,dx,dy,cosine,iRescaleIntercept,iRescaleSlope,dtype)

            images = []
            for imageFile in self.imageFiles[value]:
                reader = gdcm.Reader()
                reader.SetFileName(imageFile[1])
                # Get the DICOM File structure
                if not reader.Read():
                    print (imageFile[1], "Not a valid DICOM file")
                    sys.exit(1)
                file = reader.GetFile()
                if (file):                
                    sf = gdcm.StringFilter()
                    sf.SetFile(file)
                    # print(sf.ToStringPair(gdcm.Tag(0x0020,0x0032)))
                    # Get the DataSet part of the file
                    dataset = file.GetDataSet()
                    strIP = str(dataset.GetDataElement( gdcm.Tag(0x20,0x32) ).GetValue())
                    px,py,pz = getVector(strIP)
                    # print(imageFile[1],strIP,px,py,pz,cosine)
                    images.append([imageFile[1],thru_plane_position(px,py,pz,cosine)])
                else:
                    qDebug("Cannot read image position")
            
            dcm_slices = sorted(images,key=itemgetter(1))

            spacings = numpy.diff([dcm_slice[1] for dcm_slice in dcm_slices])
            slice_spacing = numpy.mean(spacings)

            # All slices will have the same in-plane shape
            h = len(dcm_slices)
            dz = slice_spacing
            print(h,dz)

            npVolume = numpy.zeros((h, d, w), dtype=dtype)

            for i in range(len(dcm_slices)):
                ireader = gdcm.ImageReader()
                ireader.SetFileName(dcm_slices[i][0])
                # print(dcm_slices[i])
                if (not ireader.Read()):
                    print("Cannot read image", dcm_slices[i][0])
                    sys.exit(1)
                image = ireader.GetImage()
                gdcm_array = image.GetBuffer().encode("utf-8", errors="surrogateescape")
                result = numpy.frombuffer(gdcm_array, dtype=dtype)
                npVolume[i, :, :] = numpy.flipud(result.reshape(d, w).copy())
                
            # pyplot single slice
            x = numpy.arange(0.0, (w+1)*dx, dx)
            y = numpy.arange(0.0, (d+1)*dy, dy)
            z = numpy.arange(0.0, (h+1)*dz, dz)
            #pyplot.figure(dpi=200)
            #pyplot.axes().set_aspect('equal', 'datalim')
            #pyplot.set_cmap(pyplot.gray())
            #pyplot.pcolormesh(x, y, npVolume[100,:, :])

            print ("Just for debug")

            #pyplot.show()



class ProgressWatcher(gdcm.SimpleSubjectWatcher):
    #notifyProgress = Signal(float)

    def __init__(self,s,cc):
        #super(ProgressWatcher,self).__init__(self, s,cc)
        #QObject.__init__(self)
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
            #self.notifyProgress.emit(self._progress)

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
    scanDirSeries = Signal(object,object)

    def __init__(self,cnxn):
        QFileSystemModel.__init__(self)
        self.sizeRole = int(Qt.UserRole+1)
        self.dirSelected.connect(self.selDirPath)
        self.Scanning = False
        self.threadpool = QThreadPool()
        self.progress = 0.0
        self.con = cnxn
        print("Multithreading with maximum %d threads" % self.threadpool.maxThreadCount())
    
    def sizeString(self, fInfo):
        if (not fInfo.isDir()):
           return ""
        dir = QDir(fInfo.filePath())
        fileFilters = QDir.Filters(QDir.Files|QDir.System|QDir.Hidden)
        size = 0
        for filePath in dir.entryList(fileFilters):
            fi = QFileInfo(dir,filePath)
            #print(filePath,fi.isDir())
            
            if (fi.isDir()):
                #print(filePath,"is directory")
                dir1 = fi.Dir()
                for filePath1 in dir1.entryList(fileFilters):
                    fi1 = QFileInfo(dir1,filePath1)
                    if (fi1.isDir()):
                        pass
                        #print(filePath,"is directory")
                    else:
                        size += fi1.size
            else:
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
        self.scanDirSeries.emit(res[1],res[2])
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
        #self.w.notifyProgress.connect(self.scanProgress)

        # Populate Study, Series lists
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

        tag = [ gdcm.Tag(0x10, 0x20),  # 0  Patient ID
                gdcm.Tag(0x10, 0x10),  # 1  Patient Name
                gdcm.Tag(0x08, 0x50),  # 2  Accession Number
                gdcm.Tag(0x20, 0x10),  # 3  Study ID
                gdcm.Tag(0x20, 0x0d),  # 4  Study Instance UID
                gdcm.Tag(0x20, 0x0e),  # 5  Series Instance UID
                gdcm.Tag(0x20, 0x11),  # 6  Series Number
                gdcm.Tag(0x28, 0x08),  # 7  Number of Frames
                gdcm.Tag(0x20, 0x32),  # 8  Image Position
                gdcm.Tag(0x28, 0x30),  # 9  Pixel Spacing
                gdcm.Tag(0x20, 0x37),  # 10 Image Orientation Patient
                gdcm.Tag(0x28, 0x02),  # 11 Samples per pixel
                gdcm.Tag(0x28, 0x04),  # 12 Photometric Interpretation
                gdcm.Tag(0x28, 0x10),  # 13 Rows
                gdcm.Tag(0x28, 0x11),  # 14 Column
                gdcm.Tag(0x28, 0x101), # 15 BitStored
                gdcm.Tag(0x02, 0x02),  # 16 Media Storage SOP Class UID
                gdcm.Tag(0x02, 0x03),  # 17 Media Storage SOP Instance UID
                gdcm.Tag(0x02, 0x10),  # 18 Transfer Syntax
                gdcm.Tag(0x08, 0x16),  # 19 SOP Class UID
                gdcm.Tag(0x08, 0x18),  # 20 SOP Instance UID
                gdcm.Tag(0x5200, 0x9229),  # 21 Shared functional group
                gdcm.Tag(0x5200, 0x9230),  # 22 Per frame functional group
                gdcm.Tag(0x0028, 0x1050),  # 23 WindowCenter
                gdcm.Tag(0x0028, 0x1051),  # 24 WindowWidth
                gdcm.Tag(0x0028, 0x1052),  # 25 Rescale Intercept
                gdcm.Tag(0x0028, 0x1053),  # 26 Rescale Slope
                gdcm.Tag(0x0028, 0x1054),  # 27 Rescale Type
                gdcm.Tag(0x0010, 0x0030), # 28 PatientBirthDate
                gdcm.Tag(0x0010, 0x0040), # 29 PatientSex
                gdcm.Tag(0x0008, 0x0020), # 30 Study Date
                gdcm.Tag(0x0008, 0x1030), # 31 Study Description
                gdcm.Tag(0x0008, 0x0021), # 32 Series Date
                gdcm.Tag(0x0008, 0x103E), # 33 Series Description 
                gdcm.Tag(0x0008, 0x0060), # 34 Modality
                gdcm.Tag(0x0018, 0x0015), # 35 Body Part
                gdcm.Tag(0x0020, 0x0013), # 36 Image Number/Instance Number 
                gdcm.Tag(0x0020, 0x0012), # 37 Acquisition Number 
                gdcm.Tag(0x0008, 0x0008), # 38 Image Type
                gdcm.Tag(0x0018, 0x1050), # 39 Spatial Resolution
                ]
        # Define the set of tags we are interested in, may need more

        for t in tag:
            s.AdddTag(t)

        # Iterate from strPath
        dirpath = os.walk(strPath)
        for root, directories, files in dirpath:
            for directory in directories:
                      
                d = gdcm.Directory();
                nfiles = d.Load(os.path.join(root,directory));

                if (nfiles == 0): 
                    qDebug(os.path.join(root,directory)+" Empty directory")
                else:    
                    filenames = d.GetFilenames()
                    qDebug(os.path.join(root,directory)+" The number of files to scan is "+ str(len(filenames)))

                    b = s.Scan(filenames);

                    # if no files in this directory
                    dicomfiles = []
                    if (not b):
                        qDebug("No DICOM files in this directory")
                    else:
                        study_list = []
                        series_list = []
                        series_count = {}
                        image_count = {}
                        image_files = {}

                        for aFile in filenames:
                            if (s.IsKey(aFile)):  # DICOM file
                                # qDebug("Scan "+aFile)
                                is_multiframe = 0
                                is_scout = 0  # if slice location or image position = NULL: is_scout = 1 and skipped

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

                                    if (tag == t[0]):
                                        #print ("PatientID->",value)
                                        patient_id = value
                                    elif (tag == t[1]):
                                        #print ("PatientName->",value)
                                        patient_name = value
                                    elif (tag == t[28]):
                                        # print ("PatientBirthDate->",value)
                                        patient_DOB = value
                                    elif (tag == t[29]):
                                        patient_sex = value
                                    elif (tag == t[3]):
                                        # print ("StudyID->",value)
                                        study_id = value
                                    elif (tag == t[4]):
                                        studyinstance_uid = value
                                    elif (tag == t[30]):
                                        # print ("StudyDate->",value)
                                        study_date = value
                                    elif (tag == t[31]):
                                        study_description = value
                                    elif (tag == t[6]):
                                        series_num = value
                                        # print ("SeriesNum->",value)
                                    elif (tag == t[5]):
                                        # print ("SeriesInstanceUID->",value)
                                        seriesinstance_uid = value
                                    elif (tag == t[7]):
                                        # print ("NumberOfFrame->",value)
                                        if (int(value) > 1):
                                            is_multiframe = int(value)
                                        else:
                                            is_multiframe = 0
                                    elif (tag == t[18]):
                                        # print("Transfer Syntax->",value)
                                        pass
                                    elif (tag == t[19]):
                                        # print("SOP Class UID->",value)
                                        sopclass_uid = value
                                        #sop_ClassName = sopclass_uid.GetName()
                                    elif (tag == t[20]):
                                        # print("SOP Instance UID->",value)
                                        sopinstance_uid = value
                                    # increment iterator
                                    pttv.Next()

                                # For each image
                                # Find original db data
                                # SELECT pathname, filename FROM image WHERE SOPInstanceUID == sopinstance_uid
                                cur = self.con.cursor()
                                cur.execute("SELECT pathname, filename FROM image WHERE SOPInstanceUID = '%s'" % sopinstance_uid)
                                if (len(cur)==0):
                                    pass
                                elif (len(cur)>1):
                                    qDebug("Weird")
                                else:
                                    # Copy Image File
                                    for row in cur:
                                        dstFile = row[0]+'\\'+row[1]
                                    shutil.copyfile(aFile,dstFile)        

                                # new StudyInstanceUID
                                if (studyinstance_uid not in series_count.keys()):
                                    # Add to the study_list
                                    study_list.append([patient_id, patient_name, patient_DOB, patient_sex, study_id, studyinstance_uid, study_date, study_description, 0])
                                    # Add count
                                    series_count[studyinstance_uid] = 0

                                # new SeriesInstanceUID
                                if (seriesinstance_uid not in image_count.keys()):
                                    # Add to the series_list
                                    series_list.append([study_id, studyinstance_uid, series_num, seriesinstance_uid, sopclass_uid, sopinstance_uid, 0])
                                    # Add count
                                    image_count[seriesinstance_uid] = 0
                                    image_files[seriesinstance_uid] = []
                                    series_count[studyinstance_uid] += 1

                                if (is_multiframe==0):
                                    image_count[seriesinstance_uid] += 1
                                    image_files[seriesinstance_uid].append([is_multiframe,aFile])
                                else:
                                    image_count[seriesinstance_uid] += is_multiframe
                                    image_files[seriesinstance_uid].append([is_multiframe,aFile])   

                        # For each Directory
                        # Import to DB    

                        # print(series_count)
                        # print(image_count)

                        # for each study_list items update series_count from series_count(studyinstance_uid)
                        for study in study_list:
                            study[8] = series_count[study[5]]

                        # for each series_list items update images_count from image_count(seriesinstance_uid)
                        for series in series_list:
                            series[6] = image_count[series[3]]

                        #print(study_list)
                        #print(series_list)

                        # for each series_instance_uid : analysis and fill attribute


                        return study_list, series_list, image_files


if __name__ == "__main__":

    #Set up the application window
    app = QGuiApplication(sys.argv)

    # SQL Server DB Connection
    cnxn_str = ("Driver={SQL Server Native Client 11.0};"
        "Server=localhost;"
        "Database=OD3DSDB_In2Guide;"
        "UID=SA;"
        "PwD=Testing1122;")
    try:
        cnxn = pyodbc.connect(cnxn_str)
    except pyodbc.Error as err:
        qDebug("Couldn't connect to SQL Server")   

    my_StudyModel = myStudyModel()
    my_SeriesModel = studySeriesModel()
    my_StudyModel.selectRow.connect(my_SeriesModel.refreshUID)
    # my_SeriesModel.selectRow.connect()

    # Temporarily, setting default path manually
    #path = "c:\\dev\\TestData"
    path = "D:\\In2Guide_back_up_data" # \\IMGDATA_Cdrive\\OD3DDATA\\IMGDATA"

    dirModel = myDirModel(cnxn)
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
        cnxn.close()
        sys.exit(-1)
    sys.exit(app.exec_())







                        
        

