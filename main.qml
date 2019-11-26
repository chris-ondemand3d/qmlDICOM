import QtQuick 2.9
import QtQuick.Controls 1.4
import QtQuick.Layouts 1.0
import QtQml.Models 2.2

ApplicationWindow {
    visible: true
    width: 1280
    height: 480
    title: qsTr("QMLDicomLoader")

    menuBar: MenuBar {
        Menu {
            title: qsTr("File")
            MenuItem {
                text: qsTr("&Open")
                onTriggered: console.log("Open action triggered");
            }
            MenuItem {
                text: qsTr("Exit")
                onTriggered: Qt.quit();
            }
        }
    }

    // Selection in dirModel
    ItemSelectionModel {
        id: sel
        model: dirModel
    }

    TreeView {
        id: dirView
        x: 0
        y: 0
        width: 320
        height: 400

        TableViewColumn {
            title: "Name"
            role: "fileName"
            width: 200
        }
        TableViewColumn {
            title: "Size"
            role: "size"
            width: 100
        }
        model: dirModel
        rootIndex: rootPathIndex
        selection: sel

        Connections {
            target: dirView
            onDoubleClicked: {
                console.log(sel.model.data(index))
                sel.model.dirSelected(index)
            }
        }
    }

    TableView {
        id: tableviewStudy
        x: 320
        y: 0
        width: 960
        height: 240
        TableViewColumn{ role: "patientID" ; title: "PatientID" ; visible: true}
        TableViewColumn{ role: "patientName" ; title: "PatientName" ; visible: true}
        TableViewColumn{ role: "patentDOB" ; title: "PatientDOB" ; visible: true}
        TableViewColumn{ role: "patientSex" ; title: "PatientSex" ; visible: true}
        TableViewColumn{ role: "studyID"; title: "StudyID" ; visible: true}
        TableViewColumn{ role: "studyInstanceUID"; title: "StudyInstanceUID" ; visible: true}
        TableViewColumn{ role: "studyDateTime" ; title: "StudyDateTime" ; visible: true}
        TableViewColumn{ role: "studyDescription" ; title: "StudyDescription" ; visible: true}
        TableViewColumn{ role: "numberOfSeries" ; title: "NumberOfSeries" ; visible: true}
        model: myStudyModel

        onClicked: {
            console.log(row)
            myStudyModel.notifyStudyUID(row)
        }
    }


    TableView {
        id: tableViewSeries
        x: 320
        y: 250
        width: 960
        height: 150
        TableViewColumn{ role: "studyID" ; title: "StudyID" ; visible: true}
        TableViewColumn{ role: "studyInstanceUID" ; title: "StudyInstanceUID" ; visible: true}
        TableViewColumn{ role: "seriesNum" ; title: "SeriesNum" ; visible: true}
        TableViewColumn{ role: "seriesInstanceUID" ; title: "SeriesInstanceUID" ; visible: true}
        TableViewColumn{ role: "sopClassUID" ; title: "SopClassUID" ; visible: true}
        TableViewColumn{ role: "sopInstanceUID" ; title: "SopInstanceUID" ; visible: true}
        TableViewColumn{ role: "numberOfImages" ; title: "NumberOfImages" ; visible: true}
        model: studySeriesModel
    }



    statusBar: StatusBar {
        x: 0
        y: 460

        RowLayout {
            id: layout
            anchors.fill: parent
            spacing: 0

            signal reProgress(real value)
            Component.onCompleted: dirModel.scanProgressed.connect(reProgress)

            ProgressBar {
                id: progressBar
            }

            Text {
                id: status
                //                Layout.fillWidth: true
                Layout.minimumWidth: 20
                Layout.minimumHeight: 20
                text: "Ready"
            }

            Connections {
                target: layout
                onReProgress: {
                    progressBar.value = value
                    if (value < 1.0) status.text = "Scanning"
                    if (value >= 1.0) {
                        status.text = "Ready"
                    }
                }
            }

        }
    }


}
