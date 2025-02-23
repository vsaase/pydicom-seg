import os

import numpy as np
import pydicom
import pytest
import SimpleITK as sitk

from pydicom_seg import MultiClassWriter
from pydicom_seg.template import from_dcmqi_metainfo


class TestMultiClassWriter:
    def setup(self) -> None:
        self.template = from_dcmqi_metainfo(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "pydicom_seg",
                "externals",
                "dcmqi",
                "doc",
                "examples",
                "seg-example_multiple_segments_single_input_file.json",
            )
        )

    @pytest.mark.parametrize("dtype", [np.int8, np.float32])
    def test_raises_on_invalid_data_type(self, dtype: np.dtype) -> None:
        data = np.zeros((1, 1, 1), dtype=dtype)
        segmentation = sitk.GetImageFromArray(data)
        writer = MultiClassWriter(self.template)
        with pytest.raises(ValueError, match="Unsigned integer data type.*"):
            writer.write(segmentation, [])

    def test_raises_on_invalid_rank(self) -> None:
        data = np.zeros((1, 1), dtype=np.uint8)
        segmentation = sitk.GetImageFromArray(data)
        writer = MultiClassWriter(self.template)
        with pytest.raises(ValueError, match=".*3D.*"):
            writer = MultiClassWriter(self.template)
            writer.write(segmentation, [])

    def test_raises_on_invalid_component_count(self) -> None:
        data = np.zeros((1, 1, 1, 2), dtype=np.uint8)
        segmentation = sitk.GetImageFromArray(data, isVector=True)
        writer = MultiClassWriter(self.template)
        with pytest.raises(ValueError, match=".*single component per voxel"):
            writer.write(segmentation, [])

    def test_raises_on_empty_segmentation(self) -> None:
        data = np.zeros((1, 1, 1), dtype=np.uint8)
        segmentation = sitk.GetImageFromArray(data)
        writer = MultiClassWriter(self.template)
        with pytest.raises(ValueError, match=".*not contain any labels"):
            writer.write(segmentation, [])

    def test_raises_on_missing_segment_declaration(self) -> None:
        data = np.full((1, 1, 1), fill_value=4, dtype=np.uint8)
        segmentation = sitk.GetImageFromArray(data)
        writer = MultiClassWriter(self.template, skip_missing_segment=False)
        with pytest.raises(ValueError, match=".*declaration is missing.*"):
            writer.write(segmentation, [])

    def test_raises_on_empty_segmentation_after_skipped_missing_segment_declarations(
        self,
    ) -> None:
        data = np.full((1, 1, 1), fill_value=4, dtype=np.uint8)
        segmentation = sitk.GetImageFromArray(data)
        writer = MultiClassWriter(self.template, skip_missing_segment=True)
        with pytest.raises(ValueError, match="No segments found.*"):
            writer.write(segmentation, [])

    def test_full_slice_encoding(self) -> None:
        data = np.ones((1, 512, 512), dtype=np.uint8)
        segmentation = sitk.GetImageFromArray(data)
        writer = MultiClassWriter(self.template)
        ds = writer.write(segmentation, [])

        assert ds.NumberOfFrames == 1
        assert ds.Rows == 512
        assert ds.Columns == 512

    def test_shared_functional_groups_encoding(self) -> None:
        data = np.ones((1, 512, 512), dtype=np.uint8)
        segmentation = sitk.GetImageFromArray(data)
        segmentation.SetSpacing((0.8, 0.8, 5.0))
        segmentation.SetDirection((1.0, 0.0, 0.0, 0.0, -1.0, 0.0, 0.0, 0.0, 1.0))
        writer = MultiClassWriter(self.template)
        ds = writer.write(segmentation, [])

        sfg = ds.SharedFunctionalGroupsSequence[0]
        print(sfg)
        assert sfg.PixelMeasuresSequence[0].PixelSpacing[0] == 0.8
        assert sfg.PixelMeasuresSequence[0].PixelSpacing[1] == 0.8
        assert sfg.PixelMeasuresSequence[0].SliceThickness == 5.0
        assert sfg.PixelMeasuresSequence[0].SpacingBetweenSlices == 5.0
        assert all(
            [
                x == y
                for x, y in zip(
                    sfg.PlaneOrientationSequence[0].ImageOrientationPatient,
                    [1.0, 0.0, 0.0, 0.0, -1.0, 0.0],
                )
            ]
        )

    def test_slice_encoding_with_cropping(self) -> None:
        data = np.zeros((1, 512, 512), dtype=np.uint8)
        data[0, 128:-128, 64:-64] = 1
        segmentation = sitk.GetImageFromArray(data)
        writer = MultiClassWriter(self.template, inplane_cropping=True)
        ds = writer.write(segmentation, [])

        assert ds.NumberOfFrames == 1
        assert ds.Rows == 256
        assert ds.Columns == 384

    def test_slice_encoding_without_cropping(self) -> None:
        data = np.zeros((1, 512, 512), dtype=np.uint8)
        data[0, 128:-128, 64:-64] = 1
        segmentation = sitk.GetImageFromArray(data)
        writer = MultiClassWriter(self.template, inplane_cropping=False)
        ds = writer.write(segmentation, [])

        assert ds.NumberOfFrames == 1
        assert ds.Rows == 512
        assert ds.Columns == 512

    def test_multi_class_encoding(self) -> None:
        data = np.ones((1, 512, 512), dtype=np.uint8)
        data[0, 128:-128, 128:-128] = 2
        segmentation = sitk.GetImageFromArray(data)
        writer = MultiClassWriter(self.template)
        ds = writer.write(segmentation, [])

        assert ds.Rows == 512
        assert ds.Columns == 512
        assert ds.NumberOfFrames == 2
        assert (
            ds.PerFrameFunctionalGroupsSequence[0]
            .SegmentIdentificationSequence[0]
            .ReferencedSegmentNumber
            == 1
        )
        assert (
            ds.PerFrameFunctionalGroupsSequence[1]
            .SegmentIdentificationSequence[0]
            .ReferencedSegmentNumber
            == 2
        )

    def test_multi_class_slice_encoding_with_cropping(self) -> None:
        data = np.zeros((1, 512, 512), dtype=np.uint8)
        data[0, 64:128, 64:128] = 1
        data[0, -128:-64, -128:-64] = 2
        segmentation = sitk.GetImageFromArray(data)
        writer = MultiClassWriter(self.template, inplane_cropping=True)
        ds = writer.write(segmentation, [])

        assert ds.NumberOfFrames == 2
        assert ds.Rows == 384
        assert ds.Columns == 384

    def test_skip_empty_slices_multi_class(self) -> None:
        data = np.zeros((2, 512, 512), dtype=np.uint8)
        data[0, 64:128, 64:128] = 1
        data[1, -128:-64, -128:-64] = 2
        segmentation = sitk.GetImageFromArray(data)
        writer = MultiClassWriter(
            self.template, inplane_cropping=True, skip_empty_slices=True
        )
        ds = writer.write(segmentation, [])

        assert ds.NumberOfFrames == 2
        assert ds.Rows == 384
        assert ds.Columns == 384

    def test_noskip_empty_slices_multi_class(self) -> None:
        data = np.zeros((2, 512, 512), dtype=np.uint8)
        data[0, 64:128, 64:128] = 1
        data[1, -128:-64, -128:-64] = 2
        segmentation = sitk.GetImageFromArray(data)
        writer = MultiClassWriter(
            self.template, inplane_cropping=True, skip_empty_slices=False
        )
        ds = writer.write(segmentation, [])

        assert ds.NumberOfFrames == 4
        assert ds.Rows == 384
        assert ds.Columns == 384
        assert ds.pixel_array[0].any()  # slice=0, segment=1
        assert not ds.pixel_array[1].any()  # slice=1, segment=1, only zeros
        assert not ds.pixel_array[2].any()  # slice=0, segment=2, only zeros
        assert ds.pixel_array[3].any()  # slice=1, segment=2

    def test_skip_empty_slices_between_filled_slices(self) -> None:
        data = np.zeros((3, 512, 512), dtype=np.uint8)
        data[0, 64:128, 64:128] = 1
        data[2, -128:-64, -128:-64] = 1
        segmentation = sitk.GetImageFromArray(data)
        writer = MultiClassWriter(
            self.template, inplane_cropping=True, skip_empty_slices=True
        )
        ds = writer.write(segmentation, [])

        assert ds.NumberOfFrames == 2
        assert ds.Rows == 384
        assert ds.Columns == 384

    def test_missing_segment(self) -> None:
        data = np.zeros((3, 512, 512), dtype=np.uint8)
        data[0, 64:128, 64:128] = 1
        data[2, -128:-64, -128:-64] = 4
        segmentation = sitk.GetImageFromArray(data)
        writer = MultiClassWriter(self.template, skip_missing_segment=True)
        ds = writer.write(segmentation, [])

        assert ds.NumberOfFrames == 1
        assert len(ds.SegmentSequence) == 1

    def test_frame_of_reference_copied_from_reference_image(self) -> None:
        data = np.ones((1, 512, 512), dtype=np.uint8)
        segmentation = sitk.GetImageFromArray(data)
        writer = MultiClassWriter(self.template)

        dummy_dcm = pydicom.dcmread(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "pydicom_seg",
                "externals",
                "dcmqi",
                "data",
                "segmentations",
                "ct-3slice",
                "01.dcm",
            )
        )

        ds = writer.write(segmentation, [dummy_dcm])

        assert ds.FrameOfReferenceUID == dummy_dcm.FrameOfReferenceUID
