import logging
from typing import List

import numpy as np
import pydicom
import SimpleITK as sitk

from pydicom_seg import writer_utils
from pydicom_seg.dicom_utils import DimensionOrganizationSequence
from pydicom_seg.segmentation_dataset import SegmentationDataset, SegmentationType

logger = logging.getLogger(__name__)


class MultiClassWriter:
    """Writer for DICOM-SEG files from multi-class segmentations.

    Writing DICOM-SEGs can be optimized in respect to the required disk
    space. Empty slices/frames of a 3D volume, containing only zeros, can
    be omitted from the frame sequence. Furthermore, the segmentation might
    only span a small area in a slice and thus can be cropped to the
    minimal enclosing bounding box.

    Example:
        ::

            segmentation = ...  # A multi-class segmentation as SimpleITK image
            series_dcms = ...  # List of `pydicom.Dataset`s related to the segmentation

            template = pydicom_seg.template.from_dcmqi_metainfo('metainfo.json')
            writer = MultiClassWriter(template)
            dcm = writer.write(segmentation, series_dcms)
            dcm.save_as('<path>')

    Args:
        template: A `pydicom.Dataset` holding all relevant meta information
            about the DICOM-SEG series. It has the same meaning as the
            `metainfo.json` file for the dcmqi binaries.
        inplane_cropping: If enabled, slices will be cropped (Rows/Columns)
            to the minimum enclosing boundingbox of all labels across all
            slices. Warning: This is an experimental feature and might not
            be supported when decoding with other frameworks / DICOM viewers.
        skip_empty_slices: If enabled, empty slices with only zeros
            (background label) will be ommited from the DICOM-SEG.
        skip_missing_segment: If enabled, just emit a warning if segment
            information is missing in the template for a specific label.
            The segment won't be included in the final DICOM-SEG.
            Otherwise, the encoding is aborted if segment information is
            missing.
        ignore_segmentation: If enabled ignore the data of the segmentation
            and write zeros.
    """

    def __init__(
        self,
        template: pydicom.Dataset,
        inplane_cropping: bool = False,
        skip_empty_slices: bool = True,
        skip_missing_segment: bool = False,
        ignore_segmentation: bool = False,
        segmentation_type: SegmentationType = SegmentationType.BINARY,
    ):
        self._inplane_cropping = inplane_cropping
        self._skip_empty_slices = skip_empty_slices
        self._skip_missing_segment = skip_missing_segment
        self._ignore_segmentation = ignore_segmentation
        self._template = template
        self._segmentation_type = segmentation_type

    def write(
        self, segmentation: sitk.Image, source_images: List[pydicom.Dataset]
    ) -> pydicom.Dataset:
        """Writes a DICOM-SEG dataset from a segmentation image and the
        corresponding DICOM source images.

        Args:
            segmentation: A `SimpleITK.Image` with integer labels and a single
                component per spatial location.
            source_images: A list of `pydicom.Dataset` which are the
                source images for the segmentation image.

        Returns:
            A `pydicom.Dataset` instance with all necessary information and
            meta information for writing the dataset to disk.
        """
        if segmentation.GetDimension() != 3:
            raise ValueError("Only 3D segmentation data is supported")

        if segmentation.GetNumberOfComponentsPerPixel() > 1:
            raise ValueError(
                "Multi-class segmentations can only be "
                "represented with a single component per voxel"
            )
        if not self._ignore_segmentation:
            if self._segmentation_type == SegmentationType.BINARY and segmentation.GetPixelID() not in [
                sitk.sitkUInt8,
                sitk.sitkUInt16,
                sitk.sitkUInt32,
                sitk.sitkUInt64,
            ]:
                raise ValueError(
                    "Unsigned integer data type required for binary segmentation")

            if self._segmentation_type == SegmentationType.FRACTIONAL and segmentation.GetPixelID() not in [
                sitk.sitkFloat32,
                sitk.sitkFloat64,
            ]:
                raise ValueError(
                    "Float data type required for fractional segmentation")

        # TODO Add further checks if source images are from the same series
        slice_to_source_images = self._map_source_images_to_segmentation(
            segmentation, source_images
        )

        # Check if all present labels where declared in the DICOM template
        declared_segments = set(
            [x.SegmentNumber for x in self._template.SegmentSequence]
        )

        if self._segmentation_type == SegmentationType.FRACTIONAL:
            assert len(declared_segments) == 1



        # Just use the declared segment from the template when ignoring the segmentation or processing fractional input
        if self._ignore_segmentation or self._segmentation_type == SegmentationType.FRACTIONAL:
            labels_to_process = declared_segments
        else:
            label_statistics_filter = sitk.LabelStatisticsImageFilter()
            label_statistics_filter.Execute(segmentation, segmentation)
            # Compute unique labels and their respective bounding boxes
            unique_labels = set(
                [x for x in label_statistics_filter.GetLabels() if x != 0])
            if len(unique_labels) == 0:
                raise ValueError("Segmentation does not contain any labels")
            missing_declarations = unique_labels.difference(declared_segments)
            if missing_declarations:
                missing_segment_numbers = ", ".join(
                    [str(x) for x in missing_declarations])
                message = (
                    f"Skipping segment(s) {missing_segment_numbers}, since their "
                    "declaration is missing in the DICOM template"
                )
                if not self._skip_missing_segment:
                    raise ValueError(message)
                logger.warning(message)
            labels_to_process = unique_labels.intersection(declared_segments)

            # Compute bounding boxes for each present label and optionally restrict
            # the volume to serialize to the joined maximum extent
            bboxs = {
                x: label_statistics_filter.GetBoundingBox(x) for x in labels_to_process
            }

        if not labels_to_process:
            raise ValueError("No segments found for encoding as DICOM-SEG")

        if self._inplane_cropping:
            min_x, min_y, _ = np.min([x[::2]
                                     for x in bboxs.values()], axis=0).tolist()
            max_x, max_y, _ = (
                np.max([x[1::2] for x in bboxs.values()], axis=0) + 1
            ).tolist()
            logger.info(
                "Serializing cropped image planes starting at coordinates "
                f"({min_x}, {min_y}) with size ({max_x - min_x}, {max_y - min_y})"
            )
        else:
            min_x, min_y = 0, 0
            max_x, max_y = segmentation.GetWidth(), segmentation.GetHeight()
            logger.info(
                f"Serializing image planes at full size ({max_x}, {max_y})")

        # Create target dataset for storing serialized data
        result = SegmentationDataset(
            reference_dicom=source_images[0] if source_images else None,
            rows=max_y - min_y,
            columns=max_x - min_x,
            segmentation_type=self._segmentation_type,
        )
        dimension_organization = DimensionOrganizationSequence()
        dimension_organization.add_dimension(
            "ReferencedSegmentNumber", "SegmentIdentificationSequence"
        )
        dimension_organization.add_dimension(
            "ImagePositionPatient", "PlanePositionSequence"
        )
        result.add_dimension_organization(dimension_organization)
        writer_utils.copy_segmentation_template(
            target=result,
            template=self._template,
            segments=labels_to_process,
            skip_missing_segment=self._skip_missing_segment,
        )
        writer_utils.set_shared_functional_groups_sequence(
            target=result, segmentation=segmentation
        )

        if self._ignore_segmentation:
            buffer = np.zeros(sitk.GetArrayFromImage(segmentation).shape)
        else:
            buffer = sitk.GetArrayFromImage(segmentation)
        for segment in labels_to_process:
            logger.info(f"Processing segment {segment}")

            if self._skip_empty_slices:
                bbox = bboxs[segment]
                min_z, max_z = bbox[4], bbox[5] + 1
            else:
                min_z, max_z = 0, segmentation.GetDepth()
            logger.info(
                "Total number of slices that will be processed for segment "
                f"{segment} is {max_z - min_z} (inclusive from {min_z} to {max_z})"
            )

            skipped_slices = []
            for slice_idx in range(min_z, max_z):
                frame_index = (min_x, min_y, slice_idx)
                frame_position = segmentation.TransformIndexToPhysicalPoint(
                    frame_index)

                if self._segmentation_type == SegmentationType.BINARY:
                    frame_data = np.equal(
                        buffer[slice_idx, min_y:max_y, min_x:max_x], segment
                    ).astype(np.uint8)
                elif self._segmentation_type == SegmentationType.FRACTIONAL:
                    frame_data = buffer[slice_idx,
                                        min_y:max_y, min_x:max_x]

                if self._skip_empty_slices and not frame_data.any():
                    skipped_slices.append(slice_idx)
                    continue

                frame_fg_item = result.add_frame(
                    data=frame_data,
                    referenced_segment=segment,
                    referenced_images=slice_to_source_images[slice_idx],
                )

                frame_fg_item.FrameContentSequence = [pydicom.Dataset()]
                frame_fg_item.FrameContentSequence[0].DimensionIndexValues = [
                    segment,  # Segment number
                    slice_idx - min_z + 1,  # Slice index within cropped volume
                ]
                frame_fg_item.PlanePositionSequence = [pydicom.Dataset()]
                frame_fg_item.PlanePositionSequence[0].ImagePositionPatient = [
                    f"{x:e}" for x in frame_position
                ]

            if skipped_slices:
                logger.info(
                    f"Skipped empty slices for segment {segment}: "
                    f'{", ".join([str(x) for x in skipped_slices])}'
                )

        # Encode all frames into a bytearray
        if self._inplane_cropping or self._skip_empty_slices:
            num_encoded_bytes = len(result.PixelData)
            max_encoded_bytes = (
                segmentation.GetWidth() *
                segmentation.GetHeight() *
                segmentation.GetDepth() *
                len(result.SegmentSequence) //
                8
            )
            savings = (1 - num_encoded_bytes / max_encoded_bytes) * 100
            logger.info(
                f"Optimized frame data length is {num_encoded_bytes:,}B "
                f"instead of {max_encoded_bytes:,}B (saved {savings:.2f}%)"
            )

        result.SegmentsOverlap = "NO"

        return result

    def _map_source_images_to_segmentation(
        self, segmentation: sitk.Image, source_images: List[pydicom.Dataset]
    ) -> List[List[pydicom.Dataset]]:
        """Maps an list of source image datasets to the slices of a
        SimpleITK image.

        Args:
            segmentation: A `SimpleITK.Image` with integer labels and a single
                component per spatial location.
            source_images: A list of `pydicom.Dataset` which are the
                source images for the segmentation image.

        Returns:
            A `list` with a `list` for each slice, which contains the mapped
            `pydicom.Dataset` instances for that slice location. Slices can
            have zero or more matched datasets.
        """
        result: List[List[pydicom.Dataset]] = [
            list() for _ in range(segmentation.GetDepth())
        ]
        for source_image in source_images:
            position = [float(x) for x in source_image.ImagePositionPatient]
            index = segmentation.TransformPhysicalPointToIndex(position)
            if index[2] < 0 or index[2] >= segmentation.GetDepth():
                continue
            # TODO Add reverse check if segmentation is contained in image
            result[index[2]].append(source_image)
        slices_mapped = sum(len(x) > 0 for x in result)
        logger.info(
            f"{slices_mapped} of {segmentation.GetDepth()} slices"
            "mapped to source DICOM images"
        )
        return result
