# -*- coding: utf-8 -*-

import os

from qgis.PyQt.QtCore import pyqtSlot
from qgis.PyQt.QtWidgets import QMessageBox, QFileDialog
from qgis.PyQt import uic

from gml_application_schema_toolbox.core.settings import settings
from gml_application_schema_toolbox.gui.import_gmlas_panel import ImportGmlasPanel
from gml_application_schema_toolbox.gui.import_xml_panel import ImportXmlPanel

WIDGET, BASE = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', 'ui', 'import_panel.ui'))


class ImportPanel(BASE, WIDGET):

    def __init__(self, parent=None):
        super(ImportPanel, self).__init__(parent)
        self.setupUi(self)

        self.gmlas_panel = self.addImportPanel(
            self.tr("Import using GMLAS driver"),
            ImportGmlasPanel())

        self.xml_panel = self.addImportPanel(
            self.tr("Import as XML"),
            ImportXmlPanel())

        if settings.value('default_import_method') == 'gmlas':
            self.importTypeCombo.setCurrentIndex(
                self.importTypeCombo.findData(self.gmlas_panel))
        if settings.value('default_import_method') == 'xml':
            self.importTypeCombo.setCurrentIndex(
                self.importTypeCombo.findData(self.xml_panel))

    def addImportPanel(self, text, panel):
        self.stackedWidget.addWidget(panel)
        self.importTypeCombo.addItem(text, panel)
        return panel

    @pyqtSlot(int)
    def on_importTypeCombo_currentIndexChanged(self, index):
        self.stackedWidget.setCurrentWidget(self.importTypeCombo.currentData())
