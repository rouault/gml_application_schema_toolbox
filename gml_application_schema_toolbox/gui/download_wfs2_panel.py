# -*- coding: utf-8 -*-

import os
import owslib_hacks
import owslib
from owslib.wfs import WebFeatureService
from owslib.feature.wfs200 import WFSCapabilitiesReader
from tempfile import NamedTemporaryFile
import logging

from qgis.core import QgsMessageLog, QgsCoordinateTransform, QgsCoordinateReferenceSystem
from qgis.utils import iface

from qgis.PyQt.QtCore import (
    Qt, pyqtSignal, pyqtSlot,
    QSettings,
    QUrl, QFile, QIODevice)
# from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import QMessageBox, QFileDialog, QListWidgetItem
from qgis.PyQt.QtXml import QDomDocument
from qgis.PyQt import uic

from .xml_dialog import XmlDialog

WIDGET, BASE = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', 'ui', 'download_wfs2_panel.ui'))

data_folder = '/home/qgis/qgisgmlas/data'


class QgsMessageLogHandler(logging.Handler):

    def __init__(self, tag=None):
        super(QgsMessageLogHandler, self).__init__()
        self.tag = tag

    def emit(self, record):
        try:
            msg = self.format(record)
            QgsMessageLog.logMessage(msg, self.tag)
            self.flush()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


owslib_logger = logging.getLogger('owslib')
owslib_logger.setLevel(logging.DEBUG)

owslib_handler = None
for handler in owslib_logger.handlers:
    if handler.__class__.__name__ == QgsMessageLogHandler.__name__:
        owslib_handler = handler
        break
if owslib_handler is None:
    owslib_handler = QgsMessageLogHandler('owslib')
    owslib_handler.setLevel(logging.DEBUG)
    owslib_logger.addHandler(owslib_handler)


class DownloadWfs2Panel(BASE, WIDGET):

    file_downloaded = pyqtSignal(str)

    def __init__(self, parent=None):
        super(DownloadWfs2Panel, self).__init__(parent)
        self.setupUi(self)

        self.downloadProgressBar.setVisible(False)

        self.uriComboBox.addItem('http://geoserv.weichand.de:8080/geoserver/wfs')
        self.uriComboBox.addItem('https://wfspoc.brgm-rec.fr/geoserver/ows')
        self.uriComboBox.addItem('https://wfspoc.brgm-rec.fr/constellation/WS/wfs/BRGM:GWML2')
        self.uriComboBox.addItem('http://geoserverref.brgm-rec.fr/geoserver/ows')
        self.uriComboBox.addItem('http://minerals4eu.brgm-rec.fr/deegree/services/m4eu')

    def wfs(self):
        uri = self.uriComboBox.currentText()
        return WebFeatureService(url=uri, version='2.0.0')

    @pyqtSlot()
    def on_getCapabilitiesButton_clicked(self):
        wfs = self.wfs()

        self.featureTypesListWidget.clear()
        for feature_type in list(wfs.contents):
            item = QListWidgetItem(feature_type)
            item.setData(Qt.UserRole, feature_type)
            self.featureTypesListWidget.addItem(item)

        self.storedQueriesListWidget.clear()
        for stored_query in list(wfs.storedqueries):
            self.storedQueriesListWidget.addItem(stored_query.id)

    @pyqtSlot()
    def on_showCapabilitiesButton_clicked(self):
        XmlDialog(self, self.wfs().getcapabilities().read()).exec_()
        # url = WFSCapabilitiesReader().capabilities_url(self.uri())
        # QDesktopServices.openUrl(QUrl(url))

    @pyqtSlot()
    def on_outputPathButton_clicked(self):
        current_path = self.outputPathLineEdit.text()
        cur_dir = os.path.dirname(current_path) if current_path else ''
        path, filter = QFileDialog.getSaveFileName(self,
            self.tr("Select output file"),
            cur_dir,
            self.tr("GML Files (*.gml *.xml)"))
        if path:
            if os.path.splitext(path)[1] == '':
                path = '{}.gml'.format(path)
            self.outputPathLineEdit.setText(path)

    @pyqtSlot()
    def on_downloadButton_clicked(self):
        self.downloadProgressBar.setValue(0)
        self.downloadProgressBar.setVisible(True)
        self.setCursor(Qt.WaitCursor)
        try:
            if self.datasetsTabWidget.currentIndex() == 0:
                out = self.download()
            if self.datasetsTabWidget.currentIndex() == 1:
                out = self.download_stored_query()
        finally:
            self.downloadProgressBar.setVisible(False)
            self.unsetCursor()
        if out is not None:
            self.file_downloaded.emit(out)

    def selected_typenames(self):
        typenames = []
        for item in self.featureTypesListWidget.selectedItems():
            typenames.append(item.data(Qt.UserRole))
        return typenames

    def _get_bbox(self, wfs):
        """
        Get the selected bbox in the default CRS of the first selected layer.
        """
        default_crs_name = wfs.contents[self.selected_typenames()[0]].crsOptions[0]
        default_crs = QgsCoordinateReferenceSystem.fromOgcWmsCrs(str(default_crs_name))
        assert default_crs.isValid()
        bbox_crs = iface.mapCanvas().mapSettings().destinationCrs()
        assert bbox_crs.isValid()
        transform = QgsCoordinateTransform(bbox_crs, default_crs)
        bbox = [float(x) for x in self.bboxWidget.value().split(',')]
        point1 = transform.transform(bbox[0], bbox[1])
        point2 = transform.transform(bbox[2], bbox[3])
        return [point1.x(), point1.y(), point2.x(), point2.y(), default_crs_name]

    def download(self):
        wfs = self.wfs()

        typenames = self.selected_typenames()
        if len(typenames) == 0:
            return

        params = {
            'typename': ','.join(typenames),
            'maxfeatures': self.featureLimitBox.value(),
        }

        if self.bboxGroupBox.isChecked():
            params['bbox'] = self._get_bbox(wfs)

        try:
            response = wfs.getfeature(**params)
        except owslib.util.ServiceException as e:
            QMessageBox.critical(self, 'ServiceException', str(e))
            return
        xml = response.read()

        XmlDialog(self, xml).exec_()

        doc = QDomDocument()
        if not doc.setContent(xml):
            return
        root = doc.documentElement()
        exception = root.firstChildElement('ows:Exception')
        if not exception.isNull():
            QMessageBox.critical(self,
                                 'ows:Exception',
                                 exception.text())
            return

        path = self.outputPathLineEdit.text()
        if path == '':
            with NamedTemporaryFile(mode="w+t", suffix='.gml', delete=False) as out:
                out.write(xml)
                path = out.name
        else:
            with open(path, 'w') as out:
                out.write(xml)

        return path

    def download_stored_query(self):
        pass
