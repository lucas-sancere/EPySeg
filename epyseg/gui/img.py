import traceback
import logging

from epyseg.postprocess.gui import PostProcessGUI
from epyseg.uitools.blinker import Blinker
from PyQt5.QtWidgets import QDialog, QDialogButtonBox
from PyQt5.QtWidgets import QWidget, QApplication, QGridLayout, QTabWidget
from PyQt5 import QtCore
from epyseg.deeplearning.augmentation.generators.data import DataGenerator
from epyseg.gui.open import OpenFileOrFolderWidget
from epyseg.gui.preview import crop_or_preview
from PyQt5.QtWidgets import QSpinBox, QComboBox, QVBoxLayout, QLabel, QCheckBox, QRadioButton, QButtonGroup, QGroupBox, \
    QDoubleSpinBox
from PyQt5.QtCore import Qt
from epyseg.img import Img
import sys
import os
import json

# logging
from epyseg.tools.logger import TA_logger
logger = TA_logger()

class image_input_settings(QDialog):

    def __init__(self, parent_window=None, show_channel_nb_change_rules=False, show_overlap=False, show_input=False,
                 show_output=False, allow_ROI=False,
                 show_predict_output=False, show_preprocessing=False, show_tiling=False, show_normalization=False,
                 input_mode_only=False, allow_wild_cards_in_path=False, show_preview=False, model_inputs=None, model_outputs=None,
                 _is_dialog=False, show_HQ_settings=False, label_input='Dataset', show_run_post_process=False):

        super().__init__(parent=parent_window)

        self.first_image = None
        self.first_mask = None
        self.show_overlap = show_overlap
        self.show_output = show_output
        self.allow_ROI = allow_ROI  # allow to draw ROI on preview
        self.show_preview = show_preview  # show preview or not
        self.show_predict_output = show_predict_output
        self.show_preprocessing = show_preprocessing
        self._is_dialog = _is_dialog
        self.show_tiling = show_tiling
        self.show_normalization = show_normalization
        self.show_input = show_input
        self.show_channel_nb_change_rules = show_channel_nb_change_rules
        self.input_mode_only = input_mode_only
        self.allow_wild_cards_in_path = allow_wild_cards_in_path
        # change soft behaviour if channels need be selected
        self.is_input_channel_selection_necessary = False
        self.is_output_channel_selection_necessary = False
        self.model_inputs = model_inputs
        self.model_outputs = model_outputs
        self.show_HQ_settings = show_HQ_settings
        self.show_run_post_process=show_run_post_process
        self.initUI(label_input=label_input)
        self.blinker = Blinker()

    def initUI(self, label_input='Dataset'):

        if not self.input_mode_only:
            self.tabs = QTabWidget(self)
            self.input_tab = QWidget()
            self.output_tab = QWidget()
            self.tabs.addTab(self.input_tab, 'Input')
            self.tabs.addTab(self.output_tab, 'Output')

        OpenFileOrFolderWidget.finalize_text_change = self.check_input
        self.open_input_button = OpenFileOrFolderWidget(parent_window=self, add_timer_to_changetext=True,
                                                        show_ok_or_not_icon=True, label_text=label_input,
                                                        show_size=True)
        self.nb_inputs = 0
        self.input_preprocessing_group = QGroupBox('Pre processing')
        self.input_preprocessing_group.setEnabled(True)

        input_preprocessing_group_layout = QGridLayout()
        input_preprocessing_group_layout.setAlignment(Qt.AlignTop)
        input_preprocessing_group_layout.setHorizontalSpacing(3)
        input_preprocessing_group_layout.setVerticalSpacing(3)

        # pre processing input
        self.negative_label = QLabel(
            'Most models were trained with a dark background')
        self.negative_label.setWordWrap(True)
        self.invert_chkbox = QCheckBox('Invert (negative) image (no preview)')
        self.invert_chkbox.setChecked(False)

        # arrange predict tab
        input_preprocessing_group_layout.addWidget(self.negative_label, 1, 0)
        input_preprocessing_group_layout.addWidget(self.invert_chkbox, 1, 1)

        self.input_preprocessing_group.setLayout(input_preprocessing_group_layout)
        self.tiling_group = QGroupBox('Tiling')
        self.tiling_group.setEnabled(True)

        tiling_goup_layout = QGridLayout()
        tiling_goup_layout.setAlignment(Qt.AlignTop)
        tiling_goup_layout.setColumnStretch(0, 12.5)
        tiling_goup_layout.setColumnStretch(1, 37.5)
        tiling_goup_layout.setColumnStretch(2, 12.5)
        tiling_goup_layout.setColumnStretch(3, 37.5)
        tiling_goup_layout.setHorizontalSpacing(3)
        tiling_goup_layout.setVerticalSpacing(3)

        tile_width_pred_label = QLabel('Width')
        self.tile_width_pred = QSpinBox()
        self.tile_width_pred.setSingleStep(1)
        self.tile_width_pred.setRange(32, 1_000_000)  # 1_000_000 makes no sense but anyway
        self.tile_width_pred.setValue(256)
        tile_height_pred_label = QLabel('Height')
        self.tile_height_pred = QSpinBox()
        self.tile_height_pred.setSingleStep(1)
        self.tile_height_pred.setRange(32, 1_000_000)  # 1_000_000 makes no sense but anyway
        self.tile_height_pred.setValue(256)

        if self.show_overlap:
            # tile overlap width/height. This is used to reconstruct output from model predictions
            tile_overlap_width_label = QLabel('Overlap width')
            self.tile_overlap_width = QSpinBox()
            self.tile_overlap_width.setSingleStep(2)
            self.tile_overlap_width.setRange(0, 1_000_000)  # 1_000_000 makes no sense but anyway
            self.tile_overlap_width.setValue(32)
            tile_overlap_height_label = QLabel('Overlap height')
            self.tile_overlap_height = QSpinBox()
            self.tile_overlap_height.setSingleStep(2)
            self.tile_overlap_height.setRange(0, 1_000_000)  # 1_000_000 makes no sense but anyway
            self.tile_overlap_height.setValue(32)

        # arrange predict tab
        tiling_goup_layout.addWidget(tile_width_pred_label, 1, 0)
        tiling_goup_layout.addWidget(self.tile_width_pred, 1, 1)
        tiling_goup_layout.addWidget(tile_height_pred_label, 2, 0)
        tiling_goup_layout.addWidget(self.tile_height_pred, 2, 1)
        if self.show_overlap:
            tiling_goup_layout.addWidget(tile_overlap_width_label, 1, 2)
            tiling_goup_layout.addWidget(self.tile_overlap_width, 1, 3)
            tiling_goup_layout.addWidget(tile_overlap_height_label, 2, 2)
            tiling_goup_layout.addWidget(self.tile_overlap_height, 2, 3)
        self.tiling_group.setLayout(tiling_goup_layout)

        # normalization group
        self.input_normalization_group = QGroupBox('Normalization')
        self.input_normalization_group.setEnabled(True)

        # groupBox layout
        self.input_normalization_layout = QGridLayout()
        self.input_normalization_layout.setAlignment(Qt.AlignTop)
        self.input_normalization_layout.setColumnStretch(0, 25)
        self.input_normalization_layout.setColumnStretch(1, 37.5)
        # self.input_normalization_layout.setColumnStretch(0, 25)
        self.input_normalization_layout.setColumnStretch(2, 37.5)
        self.input_normalization_layout.setHorizontalSpacing(3)
        self.input_normalization_layout.setVerticalSpacing(3)
        # self.input_normalization_layout.setContentsMargins(0, 0, 0, 0)

        # method for normalization
        self.clip_by_freq_label = QLabel('Remove outliers (intensity frequency)')
        self.clip_by_freq_combo = QComboBox()

        for method in Img.clipping_methods:
            self.clip_by_freq_combo.addItem(method)
        # self.clip_by_freq_combo.addItem('ignore outliers')
        # self.clip_by_freq_combo.addItem('+')
        # self.clip_by_freq_combo.addItem('+/-')
        # self.clip_by_freq_combo.addItem('-')
        self.clip_by_freq_combo.currentTextChanged.connect(self.clip_method_changed)

        self.clip_by_freq_range = QDoubleSpinBox()
        self.clip_by_freq_range.setRange(0., 0.25)
        self.clip_by_freq_range.setSingleStep(0.01)
        self.clip_by_freq_range.setValue(0.05)
        self.clip_by_freq_range.setEnabled(False)

        input_normalization_type_label = QLabel('Method')
        self.input_normalization = QComboBox()
        for method in Img.normalization_methods:
            self.input_normalization.addItem(method)
        self.input_normalization.currentTextChanged.connect(self.input_norm_changed)

        input_b2label = QLabel('Per channel ?')
        self.input_b2 = QCheckBox('yes')
        self.input_b2.setChecked(True)
        input_normalization_range_label = QLabel('Range')
        self.input_norm_range = QComboBox()
        for rng in Img.normalization_ranges:
            self.input_norm_range.addItem(str(rng))

        # arrange normalization groupbox
        self.input_normalization_layout.addWidget(self.clip_by_freq_label, 0, 0)
        self.input_normalization_layout.addWidget(self.clip_by_freq_combo, 0, 1, 1,3)
        self.input_normalization_layout.addWidget(self.clip_by_freq_range, 0, 5)
        self.input_normalization_layout.addWidget(input_normalization_type_label, 1, 0)
        self.input_normalization_layout.addWidget(self.input_normalization, 1, 1)
        self.input_normalization_layout.addWidget(input_b2label, 1, 2)
        self.input_normalization_layout.addWidget(self.input_b2, 1, 3)
        self.input_normalization_layout.addWidget(input_normalization_range_label, 1, 4)
        self.input_normalization_layout.addWidget(self.input_norm_range, 1, 5)
        self.input_normalization_group.setLayout(self.input_normalization_layout)

        self.channel_increase_or_reduction_rule = QGroupBox('Channel number')
        self.channel_increase_or_reduction_rule.setEnabled(True)

        channel_increase_or_reduction_goup_layout = QGridLayout()
        channel_increase_or_reduction_goup_layout.setAlignment(Qt.AlignTop)
        channel_increase_or_reduction_goup_layout.setColumnStretch(0, 25)
        channel_increase_or_reduction_goup_layout.setColumnStretch(1, 75)
        channel_increase_or_reduction_goup_layout.setHorizontalSpacing(3)
        channel_increase_or_reduction_goup_layout.setVerticalSpacing(3)

        input_channel_label = QLabel('Channel of interest (COI)')
        channel_increase_or_reduction_goup_layout.addWidget(input_channel_label, 5, 0)
        self.input_channel_of_interest = QComboBox()
        self.input_channel_of_interest.currentIndexChanged.connect(self._input_channel_changed)
        channel_increase_or_reduction_goup_layout.addWidget(self.input_channel_of_interest, 5, 1)

        input_channel_reduction_rule_label = QLabel('Rule to reduce nb of channels (if needed)')
        channel_increase_or_reduction_goup_layout.addWidget(input_channel_reduction_rule_label, 6, 0)
        self.channel_input_reduction_rule = QComboBox()
        self.channel_input_reduction_rule.addItem('copy the COI to all available channels')
        self.channel_input_reduction_rule.addItem('force copy the COI to all available '
                                                  'channels even if nb of channels is ok')
        self.channel_input_reduction_rule.addItem('remove extra channels')
        channel_increase_or_reduction_goup_layout.addWidget(self.channel_input_reduction_rule, 6, 1, 1, 2)

        input_channel_augmentation_rule_label = QLabel('Rule to increase nb of channels (if needed)')
        channel_increase_or_reduction_goup_layout.addWidget(input_channel_augmentation_rule_label, 7, 0)
        self.channel_input_augmentation_rule = QComboBox()
        self.channel_input_augmentation_rule.addItem('copy the COI to all channels')
        self.channel_input_augmentation_rule.addItem('force copy the COI to all available channels even if nb of channels is ok')
        self.channel_input_augmentation_rule.addItem('copy the COI to missing channels only')
        self.channel_input_augmentation_rule.addItem('add empty channels (0 filled)')
        channel_increase_or_reduction_goup_layout.addWidget(self.channel_input_augmentation_rule, 7, 1, 1, 2)

        self.channel_increase_or_reduction_rule.setLayout(channel_increase_or_reduction_goup_layout)

        crop_info_label = QLabel('If ROI should be used for training, please draw a rect over the image')
        input_preview_label = QLabel('Preview (COI)')
        self.image_cropper_UI = crop_or_preview(preview_only=not self.allow_ROI)

        self.output_predictions_group = QGroupBox('Output predictions to')
        self.output_predictions_group.setEnabled(True)

        # groupBox layout
        self.output_predictions_group_layout = QGridLayout()
        self.output_predictions_group_layout.setAlignment(Qt.AlignTop)
        self.output_predictions_group_layout.setColumnStretch(0, 25)
        self.output_predictions_group_layout.setColumnStretch(1, 75)
        self.output_predictions_group_layout.setHorizontalSpacing(3)
        self.output_predictions_group_layout.setVerticalSpacing(3)

        # ask whether images are to be used in combination with TA or not
        self.auto_output = QRadioButton('Auto (path displayed below)')
        self.custom_output = QRadioButton('Custom output directory')
        self.ta_output_style = QRadioButton('Tissue Analyzer mode')
        predict_output_radio_group = QButtonGroup()
        # predict_output_radio_group.buttonClicked.connect(self.predict_output_mode_changed)

        # default is build a new model
        self.auto_output.setChecked(True)

        # ask user where models should be saved
        OpenFileOrFolderWidget.finalize_text_change = self.check_custom_dir
        self.output_predictions_to = OpenFileOrFolderWidget(parent_window=self, label_text='Output predictions to',
                                                            add_timer_to_changetext=True, show_ok_or_not_icon=True)
        self.output_predictions_to.setEnabled(False)

        # connect radio to output_predictions_to text
        self.auto_output.toggled.connect(self.predict_output_mode_changed)
        self.custom_output.toggled.connect(self.predict_output_mode_changed)
        self.ta_output_style.toggled.connect(self.predict_output_mode_changed)

        predict_output_radio_group.addButton(self.ta_output_style)
        predict_output_radio_group.addButton(self.auto_output)
        predict_output_radio_group.addButton(self.custom_output)

        # arrange normalization groupbox
        self.output_predictions_group_layout.addWidget(self.auto_output, 5, 0)
        self.output_predictions_group_layout.addWidget(self.ta_output_style, 5, 1)
        self.output_predictions_group_layout.addWidget(self.custom_output, 5, 2)
        self.output_predictions_group_layout.addWidget(self.output_predictions_to, 6, 0, 1, 4)
        self.output_predictions_group.setLayout(self.output_predictions_group_layout)

        # enable HQ prediction 8 times slower but much better quality of outline
        self.hq_pred = QCheckBox('High Quality predictions (up to 12 times slower but better predictions)')
        self.hq_pred.setChecked(True)

        # run post process at the end of predictions
        # TODO maybe make that simpler --> inactivate output here if one is in post process but how can I do that ??? -> not so easy think about it
        # TODO BEST OPTION or offer a set post process parameters in a button --> make it its onw class
        # self.do_post_process_after_run = QLabel('NB: The optimal segmentation will only be obtained after running the post process on the EPySeg output (click on the "Post process" tab).')

        self.enable_post_process = QCheckBox('Refine masks')
        self.enable_post_process.setChecked(False)
        self.enable_post_process.stateChanged.connect(self._enable_post_process)

        self.do_post_process_after_run = PostProcessGUI(parent_window=None)
        self.do_post_process_after_run.setEnabled(False)

        # self.do_post_process_after_run = QCheckBox('Run post process on predictions (post process output settings must be done in the post process tab)\nNB: Output folder and raw data of post process need not be set.')
        # self.do_post_process_after_run.setChecked(True)
        # # TODO make it run indeed
        # # or do not do this and let the users do the post process --> maybe simpler and nothing to recode

        # allow post process such as watersheding for the cells
        self.raw_output = QRadioButton('Raw output')
        self.post_process_filter_n_watershed = QRadioButton('Watershed and filter (only works for default models)')
        self.both = QRadioButton('Both')
        post_process_group = QButtonGroup()

        post_process_group.addButton(self.raw_output)
        post_process_group.addButton(self.post_process_filter_n_watershed)
        post_process_group.addButton(self.both)
        # predict_output_radio_group.buttonClicked.connect(self.predict_output_mode_changed)

        # default is build a new model
        self.raw_output.setChecked(True)




        # OUTPUT panel

        OpenFileOrFolderWidget.finalize_text_change = self.check_labels
        self.open_labels_button = OpenFileOrFolderWidget(parent_window=self, add_timer_to_changetext=True,
                                                         show_ok_or_not_icon=True,
                                                         label_text='Ground truth/Segmented dataset', show_size=True)
        self.nb_outputs = 0

        # output normalization group
        self.output_pre_processing_group = QGroupBox('Pre processing')
        self.output_pre_processing_group.setEnabled(True)

        # groupBox layout
        output_pre_processing_group_layout = QGridLayout()
        output_pre_processing_group_layout.setAlignment(Qt.AlignTop)
        output_pre_processing_group_layout.setColumnStretch(0, 25)
        output_pre_processing_group_layout.setColumnStretch(1, 75)
        output_pre_processing_group_layout.setHorizontalSpacing(3)
        output_pre_processing_group_layout.setVerticalSpacing(3)

        # pre processing output
        nb_dilations_label = QLabel('Dilate')

        self.nb_mask_dilations = QSpinBox()
        self.nb_mask_dilations.setSingleStep(1)
        self.nb_mask_dilations.setRange(0, 15)
        self.nb_mask_dilations.setValue(0)

        times_label = QLabel('times')

        remove_output_border_pixels_label = QLabel('Remove')

        self.remove_output_border_pixels = QSpinBox()
        self.remove_output_border_pixels.setSingleStep(1)
        self.remove_output_border_pixels.setRange(0, 100)
        self.remove_output_border_pixels.setValue(0)

        remove_output_border_pixels_label = QLabel('remove border pixels')

        # arrange normalization groupbox
        output_pre_processing_group_layout.addWidget(nb_dilations_label, 0, 0)
        output_pre_processing_group_layout.addWidget(self.nb_mask_dilations, 0, 1)
        output_pre_processing_group_layout.addWidget(times_label, 0, 2)
        output_pre_processing_group_layout.addWidget(remove_output_border_pixels_label, 11, 0)
        output_pre_processing_group_layout.addWidget(self.remove_output_border_pixels, 11, 1, 1, 2)
        self.output_pre_processing_group.setLayout(output_pre_processing_group_layout)

        # output tiling parameters
        self.groupBox_output_tiling = QGroupBox('Tiling')
        self.groupBox_output_tiling.setEnabled(True)

        # model compilation groupBox layout
        groupBox_output_tiling_layout = QGridLayout()
        groupBox_output_tiling_layout.setAlignment(Qt.AlignTop)
        groupBox_output_tiling_layout.setColumnStretch(0, 10)
        groupBox_output_tiling_layout.setColumnStretch(1, 90)
        groupBox_output_tiling_layout.setHorizontalSpacing(3)
        groupBox_output_tiling_layout.setVerticalSpacing(3)

        default_tile_width_label = QLabel('Width')
        self.tile_width = QSpinBox()
        self.tile_width.setSingleStep(1)
        self.tile_width.setRange(32, 1_000_000)  # 1_000_000 makes no sense but anyway
        self.tile_width.setValue(256)  # 128 could also  be a good value
        default_tile_height_label = QLabel('Height')
        self.tile_height = QSpinBox()
        self.tile_height.setSingleStep(1)
        self.tile_height.setRange(32, 1_000_000)  # 1_000_000 makes no sense but anyway
        self.tile_height.setValue(256)  # 128 could also  be a good value

        # arrange normalization groupbox
        groupBox_output_tiling_layout.addWidget(default_tile_width_label, 9, 0, 1, 1)
        groupBox_output_tiling_layout.addWidget(self.tile_width, 9, 1, 1, 2)
        groupBox_output_tiling_layout.addWidget(default_tile_height_label, 10, 0, 1, 1)
        groupBox_output_tiling_layout.addWidget(self.tile_height, 10, 1, 1, 2)
        self.groupBox_output_tiling.setLayout(groupBox_output_tiling_layout)

        # output normalization group
        self.output_normalization_group = QGroupBox('Normalization')
        self.output_normalization_group.setEnabled(True)

        # groupBox layout
        self.output_normalization_layout = QGridLayout()
        self.output_normalization_layout.setAlignment(Qt.AlignTop)
        self.output_normalization_layout.setHorizontalSpacing(3)
        self.output_normalization_layout.setVerticalSpacing(3)

        output_normalization_type_label = QLabel('Method')
        self.output_normalization = QComboBox()
        for method in Img.normalization_methods:
            self.output_normalization.addItem(method)
        self.output_normalization.currentTextChanged.connect(self.output_norm_changed)
        output_b2label = QLabel('Per channel ?')
        self.output_b2 = QCheckBox('yes')
        self.output_b2.setChecked(True)
        output_normalization_range_label = QLabel('Range')
        self.output_norm_range = QComboBox()
        for rng in Img.normalization_ranges:
            self.output_norm_range.addItem(str(rng))

        # arrange normalization groupbox
        self.output_normalization_layout.addWidget(output_normalization_type_label, 0,0,1,1)
        self.output_normalization_layout.addWidget(self.output_normalization,0,1,1,1)
        self.output_normalization_layout.addWidget(output_b2label,0,2,1,1)
        self.output_normalization_layout.addWidget(self.output_b2,0,3,1,1)
        self.output_normalization_layout.addWidget(output_normalization_range_label,0,4,1,1)
        self.output_normalization_layout.addWidget(self.output_norm_range,0,5,1,1)
        self.output_normalization_group.setLayout(self.output_normalization_layout)

        self.output_channel_increase_or_reduction_rule = QGroupBox('Channel number')
        self.output_channel_increase_or_reduction_rule.setEnabled(True)

        output_channel_increase_or_reduction_goup_layout = QGridLayout()
        output_channel_increase_or_reduction_goup_layout.setAlignment(Qt.AlignTop)
        output_channel_increase_or_reduction_goup_layout.setColumnStretch(0, 25)
        output_channel_increase_or_reduction_goup_layout.setColumnStretch(1, 75)
        output_channel_increase_or_reduction_goup_layout.setHorizontalSpacing(3)
        output_channel_increase_or_reduction_goup_layout.setVerticalSpacing(3)

        output_channel_label = QLabel('Channel of interest (COI)')
        output_channel_increase_or_reduction_goup_layout.addWidget(output_channel_label, 8, 0)
        self.output_channel_of_interest = QComboBox()
        self.output_channel_of_interest.currentIndexChanged.connect(self._output_channel_changed)
        output_channel_increase_or_reduction_goup_layout.addWidget(self.output_channel_of_interest, 8, 1)

        output_channel_reduction_rule_label = QLabel('Rule to reduce channels (if needed)')
        output_channel_increase_or_reduction_goup_layout.addWidget(output_channel_reduction_rule_label, 9, 0)
        self.channel_output_reduction_rule = QComboBox()
        self.channel_output_reduction_rule.addItem('copy the COI to all available channels')
        self.channel_output_reduction_rule.addItem('force copy the COI to all available '
                                                   'channels even if nb of channels is ok')
        self.channel_output_reduction_rule.addItem('remove extra channels')
        output_channel_increase_or_reduction_goup_layout.addWidget(self.channel_output_reduction_rule, 9, 1, 1, 2)

        output_channel_augmentation_rule_label = QLabel('Rule to increase channels (if needed)')
        output_channel_increase_or_reduction_goup_layout.addWidget(output_channel_augmentation_rule_label, 10, 0)
        self.channel_output_augmentation_rule = QComboBox()
        self.channel_output_augmentation_rule.addItem('copy the COI to all channels')
        self.channel_output_augmentation_rule.addItem('force copy the COI to all available channels even if nb of channels is ok')
        self.channel_output_augmentation_rule.addItem('copy the COI to missing channels only')
        self.channel_output_augmentation_rule.addItem('add empty channels (0 filled)')
        output_channel_increase_or_reduction_goup_layout.addWidget(self.channel_output_augmentation_rule, 10, 1, 1, 2)

        self.output_channel_increase_or_reduction_rule.setLayout(output_channel_increase_or_reduction_goup_layout)

        # now both previews to gain space
        output_preview_label = QLabel('Preview (COI)')
        self.mask_preview = crop_or_preview(preview_only=True)

        input_v_layout = QVBoxLayout()
        input_v_layout.setAlignment(Qt.AlignTop)
        if self.show_input:
            input_v_layout.addWidget(self.open_input_button)
        else:
            self.open_input_button.hide()
        if self.show_preprocessing:
            input_v_layout.addWidget(self.input_preprocessing_group)
        if self.show_tiling:
            input_v_layout.addWidget(self.tiling_group)
        if self.show_normalization:
            input_v_layout.addWidget(self.input_normalization_group)
        if self.show_channel_nb_change_rules:
            input_v_layout.addWidget(self.channel_increase_or_reduction_rule)
        if self.show_preview:
            if self.show_input and self.show_output:
                input_v_layout.addWidget(crop_info_label)
            input_v_layout.addWidget(input_preview_label)
            input_v_layout.addWidget(self.image_cropper_UI)

        if self.show_HQ_settings:
            input_v_layout.addWidget(self.hq_pred)

        if self.show_predict_output:
            input_v_layout.addWidget(self.output_predictions_group)
        else:
            self.output_predictions_to.hide()

        if self.show_run_post_process:
            input_v_layout.addWidget(self.enable_post_process)
            input_v_layout.addWidget(self.do_post_process_after_run)


        if not self.input_mode_only:
            output_v_layout = QVBoxLayout()
            output_v_layout.setAlignment(Qt.AlignTop)
            if self.show_output:
                output_v_layout.addWidget(self.open_labels_button)
            else:
                self.open_labels_button.hide()
            if self.show_preprocessing:
                output_v_layout.addWidget(self.output_pre_processing_group)
            if self.show_tiling:
                output_v_layout.addWidget(self.groupBox_output_tiling)
            if self.show_normalization:
                output_v_layout.addWidget(self.output_normalization_group)
            if self.show_channel_nb_change_rules:
                output_v_layout.addWidget(self.output_channel_increase_or_reduction_rule)
            if self.show_preview:
                output_v_layout.addWidget(output_preview_label)
                output_v_layout.addWidget(self.mask_preview)
        else:
            self.open_labels_button.hide()

        if not self.input_mode_only:
            self.input_tab.setLayout(input_v_layout)
            self.output_tab.setLayout(output_v_layout)
            table_widget_layout = QVBoxLayout()
            table_widget_layout.setAlignment(Qt.AlignTop)
            table_widget_layout.addWidget(self.tabs)
            self.setLayout(table_widget_layout)
        else:
            self.setLayout(input_v_layout)

        if self._is_dialog:
            # OK and Cancel buttons
            self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                QtCore.Qt.Horizontal, self)
            self.buttons.accepted.connect(self.check_n_accept)
            self.buttons.rejected.connect(self.reject)
            self.layout().addWidget(self.buttons)

    def _enable_post_process(self, int):
        self.do_post_process_after_run.setEnabled(self.enable_post_process.isChecked())

    def set_input_channel_selection_is_necessary(self, bool):
        self.is_input_channel_selection_necessary = bool

    def set_output_channel_selection_is_necessary(self, bool):
        self.is_output_channel_selection_necessary = bool

    def set_model_inputs(self, model_inputs):
        self.model_inputs = model_inputs

    def set_model_outputs(self, model_outputs):
        self.model_outputs = model_outputs

    def check_n_set_input_channel_selection_necessity(self):
        if not self.show_channel_nb_change_rules:
            return False
        if self.model_inputs is None:
            logger.error('please specify model input to check if channel selection is necessary or not')
            return

        # TODO need change this to a loop to accept multiple inputs or outputs
        input_coi = self.get_input_channel_of_interest()
        if input_coi is not None:
            if self.input_channel_of_interest.count() == 0:
                self.is_input_channel_selection_necessary = False
            else:
                self.is_input_channel_selection_necessary = True
        else:
            # check channel by channel if ok or not
            for idx, input in enumerate(self.model_inputs):
                channels_in_model = input[-1]
                if self.first_image is None:
                    logger.error('please select input data first to check if channel selection is necessary or not')
                    return

                if self.first_image.shape[-1] == channels_in_model:
                    self.is_input_channel_selection_necessary = False
                else:
                    self.is_input_channel_selection_necessary = True
                # REMOVE BREAK WHEN SEVERAL INPUT IMAGES ARE AVAILABLE
                break

    def check_n_set_output_channel_selection_necessity(self):
        # need compare model output to real output images
        # need perform this check on output change
        if self.model_outputs is None:
            logger.error('please specify model output to check if channel selection is necessary or not')
            return

        # need change this to a loop to accept multiple inputs or outputs
        output_coi = self.get_output_channel_of_interest()
        if output_coi is not None:
            if self.output_channel_of_interest.count() == 0:
                self.is_output_channel_selection_necessary = False
            else:
                self.is_output_channel_selection_necessary = True
        else:
            # check channel by channel if ok or not
            for idx, output in enumerate(self.model_outputs):
                channels_in_model = output[-1]
                if self.first_mask is None:
                    logger.error('please select output data first to check if channel selection is necessary or not')
                    return

                if self.first_mask.shape[-1] == channels_in_model:
                    self.is_output_channel_selection_necessary = False
                else:
                    self.is_output_channel_selection_necessary = True

                # REMOVE BREAK WHEN SEVERAL INPUT IMAGES ARE AVAILABLE
                break

    def clip_method_changed(self):
        allow_changes = not 'ignore' in self.clip_by_freq_combo.currentText()
        self.clip_by_freq_range.setEnabled(allow_changes)

    def check_custom_dir(self):
        txt = self.output_predictions_to.text()
        # do I even need to check it as long as it can be created it's ok
        if txt:
            if self.custom_output.isChecked():
                if os.path.exists(txt) and os.path.isdir(txt) and os.access(txt, os.W_OK):
                    if self.open_input_button.text() is not None:
                        # make sure the user is not trying to write to the parent folder (overwrite issue)
                        if self.output_predictions_to.text() == self.open_input_button.text() or \
                                os.path.realpath(self.output_predictions_to.text()) == os.path.realpath(self.open_input_button.text()):
                            self.output_predictions_to.set_icon_ok(False)
                            logger.error('same as the dataset input folder')
                        else:
                            self.output_predictions_to.set_icon_ok(True)
                    else:
                        self.output_predictions_to.set_icon_ok(True)
                else:
                    self.output_predictions_to.set_icon_ok(False)
                    logger.error('not a valid/existing folder or does not have write access')
            else:
                if self.ta_output_style.isChecked():
                    if os.access(txt, os.W_OK):
                        self.output_predictions_to.set_icon_ok(True)
                    else:
                        logger.error(
                            'cannot write to folder \'' + txt + '\' please change output folder and change folder rights')
                        self.output_predictions_to.set_icon_ok(False)
                else:
                    # may not work if cannot write (hard to do because can only check once the folder is created...)
                    self.output_predictions_to.set_icon_ok(True)
        else:
            self.output_predictions_to.set_icon_ok(False)
            # logger.error('You are using a custom path but have not yet set it...')

    def predict_output_mode_changed(self):
        if self.custom_output.isChecked():
            self.output_predictions_to.setEnabled(True)
            self.check_custom_dir()
        else:
            self.output_predictions_to.setEnabled(False)

    def output_norm_changed(self):
        if self.output_normalization.currentText() == Img.normalization_methods[0] \
                or self.output_normalization.currentText() == Img.normalization_methods[1]:
            self.output_norm_range.setEnabled(True)
        else:
            self.output_norm_range.setEnabled(False)

    def input_norm_changed(self):
        if self.input_normalization.currentText() == Img.normalization_methods[0] \
                or self.input_normalization.currentText() == Img.normalization_methods[1]:
            self.input_norm_range.setEnabled(True)
        else:
            self.input_norm_range.setEnabled(False)

    def _output_channel_changed(self):
        if self.first_mask is not None and self.first_mask.has_c():
            if self.output_channel_of_interest.currentIndex() != -1:
                channel_img = self.first_mask.imCopy(c=self.output_channel_of_interest.currentIndex())
                self.mask_preview.set_image(channel_img)
            else:
                self.mask_preview.set_image(self.first_mask)
        else:
            self.mask_preview.set_image(self.first_mask)

    def _input_channel_changed(self):
        if self.first_image is not None and self.first_image.has_c():
            if self.input_channel_of_interest.currentIndex() != -1:
                channel_img = self.first_image.imCopy(c=self.input_channel_of_interest.currentIndex())
                self.image_cropper_UI.set_image(channel_img)
            else:
                self.image_cropper_UI.set_image(self.first_image)
        else:
            self.image_cropper_UI.set_image(self.first_image)

    def check_labels(self):
        txt = self.open_labels_button.text()
        if txt is not None and '*' in txt:
            if not self.allow_wild_cards_in_path:
                self.first_mask = None
                self.open_labels_button.set_icon_ok(False)
                self.nb_outputs = 0
                logger.error('wild cards not allowed in names (to avoid overwrite of files with same names). Please provide a path to a folder instead...')
                return

            file_list = self.open_labels_button.get_list_using_glob()
            if file_list is not None and file_list:
                import os
                self.first_mask, can_read = self._can_read_file(file_list[0], self.output_channel_of_interest)
                self.check_n_set_output_channel_selection_necessity()
                if self.is_output_channel_selection_necessary:
                    logger.info('force output channel selection due to mismatch with model output')
                    self.output_channel_of_interest.setCurrentIndex(0)  # force select a channel
                    self._output_channel_changed()

                self.open_labels_button.set_icon_ok(can_read)
                if can_read:
                    self.nb_outputs = len(file_list)
                else:
                    self.nb_outputs = 0
            else:
                self.first_mask = None
                self.open_labels_button.set_icon_ok(False)
                self.nb_outputs = 0

        elif txt is not None:
            import os
            file_list = DataGenerator.get_list_of_images(self.open_labels_button.text())
            if file_list:
                self.first_mask, can_read = self._can_read_file(file_list[0], self.output_channel_of_interest)
                self.check_n_set_output_channel_selection_necessity()
                if self.is_output_channel_selection_necessary:
                    logger.info('force output channel selection due to mismatch with model output')
                    self.output_channel_of_interest.setCurrentIndex(0)
                    self._output_channel_changed()
                self.open_labels_button.set_icon_ok(can_read)
                if can_read:
                    self.nb_outputs = len(file_list)
                else:
                    self.nb_outputs = 0
            else:
                self.first_mask = None
                self.open_labels_button.set_icon_ok(False)
                self.nb_outputs = 0
                logger.error('error no files matching "'+str(self.open_input_button.text())+ '"')

        self._update_inputs_and_outputs_nb()

    def check_predict_dir(self):
        txt = self.open_input_button.text()

        if txt:
            if os.path.exists(txt) and os.path.isdir(txt) and os.access(txt, os.W_OK):
                self.open_input_button.set_icon_ok(True)
            else:
                self.open_input_button.set_icon_ok(False)
                logger.error('not a valid/existing folder or does not have write access')
        else:
            self.open_input_button.set_icon_ok(False)
            logger.error('not a valid/existing folder or does not have write access')

        if os.path.isdir(txt):
            if self.auto_output.isChecked():
                if txt is not None:
                    self.output_predictions_to.path.setText(
                        os.path.join(self.open_input_button.text(), 'predict/'))
                else:
                    self.output_predictions_to.path.setText('')
        else:
            if self.auto_output.isChecked():
                self.output_predictions_to.path.setText('')

    def check_input(self):
        txt = self.open_input_button.text()
        if txt is not None and '*' in txt:
            if not self.allow_wild_cards_in_path:
                self.first_image = None
                self.open_input_button.set_icon_ok(False)
                self.nb_inputs = 0
                logger.error('wild cards not allowed in names '
                             '(to avoid overwriting files with same names coming from different input folders). '
                             'Please provide a path to a single folder instead...')

                if self.auto_output.isChecked():
                    self.output_predictions_to.path.setText('')
                    self.output_predictions_to.set_icon_ok(False)
                return

            file_list = self.open_input_button.get_list_using_glob()
            if file_list is not None and file_list:
                import os
                self.first_image, can_read = self._can_read_file(file_list[0], self.input_channel_of_interest)
                self.check_n_set_input_channel_selection_necessity()
                if self.is_input_channel_selection_necessary:
                    logger.info('force input channel selection due to mismatch with model input')
                    self.input_channel_of_interest.setCurrentIndex(0)  # force select a channel
                    self._input_channel_changed()

                self.open_input_button.set_icon_ok(can_read)
                if can_read:
                    self.nb_inputs = len(file_list)
                else:
                    self.nb_inputs = 0

                if self.open_labels_button.text() is not None:
                    if self._can_read_mask(file_list[0]):
                        self.nb_outputs = self.nb_inputs
                    else:
                        self.nb_outputs = 0
            else:
                self.open_input_button.set_icon_ok(False)
                self.nb_inputs = 0
                self.first_image = None
                if self.open_labels_button.text() is not None:
                    self.open_labels_button.set_icon_ok(False)
                    self.nb_outputs = 0
        elif txt is not None:
            import os
            file_list = DataGenerator.get_list_of_images(txt)
            if file_list:
                if os.path.isdir(txt):
                    if self.auto_output.isChecked():
                        if txt is not None:
                            self.output_predictions_to.path.setText(
                                os.path.join(txt, 'predict/'))
                        else:
                            self.output_predictions_to.path.setText('')
                else:
                    if self.auto_output.isChecked():
                        # get parent dir to save in it
                        self.output_predictions_to.path.setText(os.path.join(
                            os.path.abspath(os.path.join(txt, '..')), 'predict/'))

                self.first_image, can_read = self._can_read_file(file_list[0], self.input_channel_of_interest)

                self.check_n_set_input_channel_selection_necessity()
                if self.is_input_channel_selection_necessary:
                    logger.info('force input channel selection due to mismatch with model input')
                    self.input_channel_of_interest.setCurrentIndex(0)  # force select a channel
                    self._input_channel_changed()

                self.open_input_button.set_icon_ok(can_read)
                self.nb_inputs = len(file_list)

                if self.open_labels_button.text() is not None:
                    if self._can_read_mask(file_list[0]):
                        self.nb_outputs = self.nb_inputs
                    else:
                        self.nb_outputs = 0
            else:
                self.nb_inputs = 0
                self.first_image = None
                self.open_input_button.set_icon_ok(False)
                if self.open_labels_button.text() is not None:
                    self.open_labels_button.set_icon_ok(False)
                    self.nb_outputs = 0
                if self.auto_output.isChecked():
                    self.output_predictions_to.path.setText('')
                    self.output_predictions_to.set_icon_ok(False)
                logger.error('error no files matching "' + txt + '"')
        self._update_inputs_and_outputs_nb()

    def _can_read_mask(self, path):
        # TODO replace all +'/'+ by path join
        import os
        mask_path = os.path.join(os.path.splitext(path)[0], 'handCorrection.png')
        if os.path.isfile(mask_path):
            if self._can_read_file(path, self.output_channel_of_interest):
                logger.info('TA organization detected')
                self.open_labels_button.set_icon_ok(True)
                return True
            else:
                logger.info('non-TA organization')
                self.open_labels_button.set_icon_ok(False)
        else:
            mask_path = os.path.join(os.path.splitext(path)[0], 'handCorrection.tif')
            if os.path.isfile(mask_path):
                if self._can_read_file(path, self.output_channel_of_interest):
                    logger.info('TA organization detected')
                    self.open_labels_button.set_icon_ok(True)
                    return True
                else:
                    logger.info('non-TA organization')
                    self.open_labels_button.set_icon_ok(False)
            else:
                self.open_labels_button.set_icon_ok(False)
        return False

    def _update_inputs_and_outputs_nb(self):
        info_text = 'everything seems fine'
        if self.nb_outputs == 0 or self.nb_inputs == 0 or self.nb_outputs != self.nb_inputs:
            info_text = 'there seems to be a pb\n with your input/label data\n please check'
        # print(str(self.nb_inputs) + ' / ' + str(self.nb_outputs) + " " + info_text)
        self.open_input_button.set_size(str(self.nb_inputs))
        self.open_labels_button.set_size(str(self.nb_outputs))

    def get_input_channel_of_interest(self):
        input_channel_of_interest = self.input_channel_of_interest.currentIndex()
        if input_channel_of_interest == -1:
            input_channel_of_interest = None
        else:
            input_channel_of_interest = int(self.input_channel_of_interest.currentText())
        return input_channel_of_interest

    def get_output_channel_of_interest(self):
        output_channel_of_interest = self.output_channel_of_interest.currentIndex()
        if output_channel_of_interest == -1:
            output_channel_of_interest = None
        else:
            output_channel_of_interest = int(self.output_channel_of_interest.currentText())
        return output_channel_of_interest

    def get_parameters_directly(self, blink_on_error=False):
        data = {}

        input_channel_of_interest = self.get_input_channel_of_interest()
        output_channel_of_interest = self.get_output_channel_of_interest()

        if self.show_input:
            data['inputs'] = self.get_inputs()
            if blink_on_error:
                if data['inputs'] is None or data['inputs'] == [None]:
                    self.tabs.setCurrentIndex(0)
                    logger.error('Please provide a valid input dataset (highlighted in red)')
                    self.blinker.blink(self.open_input_button)
                    return

        if self.show_preprocessing:
            data['invert'] = self.invert_chkbox.isChecked()

        if self.show_tiling:
            data['default_input_tile_width'] = self.tile_width_pred.value()
            data['default_input_tile_height'] = self.tile_height_pred.value()
            if self.show_overlap:
                data['tile_width_overlap'] = self.tile_overlap_width.value()
                data['tile_height_overlap'] = self.tile_overlap_height.value()

            if blink_on_error:
                if 'tile_width_overlap' in data:
                    if data['tile_width_overlap'] >= data['default_input_tile_width']/2:
                        self.tabs.setCurrentIndex(0)
                        logger.error('Image width overlap is bigger than image width/2, '
                                     'this does not make sense please increase tile width or decrease overlap width. '
                                     'Ideally width should be at least twice the size of the overlap.')
                        self.blinker.blink(self.tiling_group)
                        return

                if 'tile_height_overlap' in data:
                    if data['tile_height_overlap'] >= data['default_input_tile_height']/2:
                        self.tabs.setCurrentIndex(0)
                        logger.error('Image height overlap is bigger than image height/2, '
                                     'this does not make sense please increase tile height or decrease overlap height. '
                                     'Ideally height should be at least twice the size of the overlap.')
                        self.blinker.blink(self.tiling_group)
                        return

        if self.show_channel_nb_change_rules:
            data['input_channel_reduction_rule'] = self.channel_input_reduction_rule.currentText()
            data['input_channel_augmentation_rule'] = self.channel_input_augmentation_rule.currentText()
            data['input_channel_of_interest'] = input_channel_of_interest
        if self.show_normalization:
            data['input_normalization'] = {'method': self.input_normalization.currentText(),
                                           'individual_channels': self.input_b2.isChecked(),
                                           'range': self.input_norm_range.currentText()}
            data['clip_by_frequency'] = self.get_clip_by_freq()
        if self.allow_ROI:
            data['crop_parameters'] = self.image_cropper_UI.get_crop_parameters()
        if self.show_predict_output:
            data['predict_output_folder'] = \
                self.output_predictions_to.text() if not self.ta_output_style.isChecked() else 'TA_mode'
        data['hq_predictions'] = self.hq_pred.isChecked()
        if not self.input_mode_only:
            if self.show_output:
                data['outputs'] = self.get_outputs()
                if blink_on_error:
                    if data['outputs'] is None or data['outputs'] == [None]:
                        logger.error('Please provide a valid output dataset (i.e. ground truth segmentation)')
                        self.tabs.setCurrentIndex(1)
                        self.blinker.blink(self.open_labels_button)
                        return
                    elif self.nb_inputs != self.nb_outputs:
                        logger.error('The number of input images (n='+ str(self.nb_inputs)
                                     +') and output images (n='+str(self.nb_outputs)
                                     +') differ, please check your folders, '
                                      'there has to be a one to one correspondence...')
                        # print the list of files to help people
                        try:
                            # TODO modify code to add support for multiple inputs
                            list_input = DataGenerator.get_list_of_images(data['inputs'][0])
                            list_output = DataGenerator.get_list_of_images(data['outputs'][0])
                            from itertools import zip_longest
                            correspondence = dict(zip_longest((list_input), (list_output)))
                            logger.error('Actual file correspondence is:')
                            for inp, out in correspondence.items():
                                logger.error('- '+str(inp) +' --> '+str(out))
                        except:
                            traceback.print_exc()
                        self.tabs.setCurrentIndex(1)
                        self.blinker.blink(self.open_labels_button)
                        return
            if self.show_preprocessing:
                data['remove_n_border_mask_pixels'] = self.remove_output_border_pixels.value()
                data['mask_dilations'] = self.nb_mask_dilations.value()
            if self.show_tiling:
                data['default_output_tile_width'] = self.tile_width.value()
                data['default_output_tile_height'] = self.tile_height.value()
            if self.show_channel_nb_change_rules:
                data['output_channel_reduction_rule'] = self.channel_output_reduction_rule.currentText()
                data['output_channel_augmentation_rule'] = self.channel_output_augmentation_rule.currentText()
                data['output_channel_of_interest'] = output_channel_of_interest
            if self.show_normalization:
                data['output_normalization'] = {'method': self.output_normalization.currentText(),
                                                'individual_channels': self.output_b2.isChecked(),
                                                'range': self.output_norm_range.currentText()}

        # print('current test', self.show_run_post_process, self.enable_post_process.isChecked())
        # allow post process
        if self.show_run_post_process:
            if self.enable_post_process.isChecked():
                # print('in here')
                data.update(self.do_post_process_after_run.get_parameters_directly())
                # print(data, self.do_post_process_after_run.get_parameters_directly())
                # maybe put refined masks in a new folder
        return data

    def get_inputs(self):
        # TODO implement the possibility yo have several inputs
        return [self.open_input_button.text()]

    def get_outputs(self):
        # TODO implement the possibility yo have several outputs
        return [self.open_labels_button.text()]

    def get_parameters(self):
        return json.dumps(self.get_parameters_directly())

    def get_clip_by_freq(self):
        if 'ignore' in self.clip_by_freq_combo.currentText():
            return {'lower_cutoff': None, 'upper_cutoff': None,
                    'channel_mode': self.input_b2.isChecked()}
        elif self.clip_by_freq_combo.currentText() == '+':
            return {'lower_cutoff': None, 'upper_cutoff': self.clip_by_freq_range.value(),
                    'channel_mode': self.input_b2.isChecked()}
        elif self.clip_by_freq_combo.currentText() == '-':
            return {'lower_cutoff': self.clip_by_freq_range.value(), 'upper_cutoff': None,
                    'channel_mode': self.input_b2.isChecked()}
        elif '/' in self.clip_by_freq_combo.currentText():
            return {'lower_cutoff': self.clip_by_freq_range.value(), 'upper_cutoff': self.clip_by_freq_range.value(),
                    'channel_mode': self.input_b2.isChecked()}
        else:
            logger.error('unknown frequency filtering')

    def _can_read_file(self, path, channels_to_update=None):
        try:
            img = Img(path)
            try:
                if img.has_c() and channels_to_update is not None:
                    # empty channel combo
                    channels_to_update.clear()
                    # add new channels to combo
                    for chan in range(img.shape[-1]):
                        channels_to_update.addItem(str(chan))
                    # deselect it
                    channels_to_update.setCurrentIndex(-1)
                    channels_to_update.update()
                if not img.has_c():
                    channels_to_update.clear()
                    channels_to_update.setCurrentIndex(-1)
                    channels_to_update.update()
            except:
                logging.error(traceback.format_exc())
            return img, True
        except:
            logger.error('could not read image ' + path)
        return None, False


    @staticmethod
    def getDataAndParameters(parent_window=None, show_overlap=False, show_input=False, show_output=False,
                             allow_ROI=False,
                             show_predict_output=False, show_preprocessing=False, show_tiling=False,
                             show_normalization=False, show_channel_nb_change_rules=False, input_mode_only=False,
                             allow_wild_cards_in_path=False,
                             show_preview=False, model_inputs=None, model_outputs=None, show_HQ_settings=False, show_run_post_process=False): #
        # get all the params for augmentation
        dialog = image_input_settings(parent_window=parent_window, show_overlap=show_overlap,
                                      show_input=show_input, show_output=show_output,
                                      allow_ROI=allow_ROI,
                                      show_predict_output=show_predict_output,
                                      show_preprocessing=show_preprocessing,
                                      show_tiling=show_tiling,
                                      show_normalization=show_normalization,
                                      show_channel_nb_change_rules=show_channel_nb_change_rules,
                                      input_mode_only=input_mode_only,
                                      allow_wild_cards_in_path=allow_wild_cards_in_path,
                                      show_preview=show_preview,
                                      model_inputs=model_inputs,
                                      model_outputs=model_outputs,
                                      _is_dialog=True,
                                      show_HQ_settings=show_HQ_settings,
                                      show_run_post_process=show_run_post_process)

        result = dialog.exec_()
        augment = dialog.get_parameters()
        return (augment, result == QDialog.Accepted)

    def check_n_accept(self):
        params = self.get_parameters_directly(blink_on_error=True)
        if isinstance(params, dict):
            self.accept()
        else:
            logger.error('You will only be allowed to press "ok" when all the required input parameters would have been entered, please fill in the red highlighted parameters and try again')

if __name__ == '__main__':
    # just for a test
    app = QApplication(sys.argv)
    augment, ok = image_input_settings.getDataAndParameters(parent_window=None,
                                                            show_normalization=True,
                                                            show_preview=True,
                                                            show_predict_output=True,
                                                            show_overlap=True, show_input=True,
                                                            show_output=True,
                                                            show_preprocessing=True,
                                                            show_tiling=True,
                                                            show_channel_nb_change_rules=True,
                                                            show_HQ_settings=True,
                                                            show_run_post_process=True)
    print(augment, ok)
    sys.exit(0)
