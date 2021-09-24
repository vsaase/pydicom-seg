# -*- coding: utf-8 -*-
from setuptools import setup

packages = \
['pydicom_seg']

package_data = \
{'': ['*'], 'pydicom_seg': ['schemas/*']}

install_requires = \
['SimpleITK>1.2.4',
 'attrs>=19.3.0,<20.0.0',
 'jsonschema>=3.2.0,<4.0.0',
 'numpy>=1.18.0,<2.0.0',
 'pydicom>=1.4.2']

setup_kwargs = {
    'name': 'pydicom-seg',
    'version': '0.3.0.dev0',
    'description': 'Python package for DICOM-SEG medical segmentation file reading and writing',
    'long_description': "# pydicom-seg\n\n[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)\n[![Python versions](https://img.shields.io/pypi/pyversions/pydicom-seg.svg)](https://img.shields.io/pypi/pyversions/pydicom-seg.svg)\n[![PyPI version](https://badge.fury.io/py/pydicom-seg.svg)](https://badge.fury.io/py/pydicom-seg)\n[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.3899003.svg)](https://doi.org/10.5281/10.5281/zenodo.3899003)\n\nReading and writing of [DICOM-SEG](http://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.8.20.html) medical image segmentation storage files using [pydicom](https://github.com/pydicom/pydicom) as DICOM serialization/deserialization library. For detailed explanations about supported functionality and usage please have a look at the [documentation](https://razorx89.github.io/pydicom-seg).\n\n## Motivation\n\nConverting DICOM-SEG files into ITK compatible data formats, commonly used for\nresearch, is made possible by the [dcmqi](https://github.com/QIICR/dcmqi)\nproject for some time. However, the project is written in C++ and offers only\naccess to the conversion via the binaries `itkimage2segimage` and\n`segimage2itkimage`. After a conversion of a DICOM-SEG file to ITK NRRD file\nformat, the user has to scan the output directory for generated files, load\nthem individually and potentially combine multiple files to the desired format.\n\nThis library aims to make this process much easier, by providing a Python\nnative implementation of reading and writing functionality with support for\n`numpy` and `SimpleITK`. Additionally, common use cases like loading\nmulti-class segmentations are supported out-of-the-box.\n\n## Installation\n\n### Install from PyPI\n\n```bash\npip install pydicom-seg\n```\n\n### Install from source\n\nThis package uses [Poetry](https://python-poetry.org/) (version >= 1.0.5) as build system.\n\n```bash\ngit clone \\\n    --recurse-submodules \\\n    https://github.com/razorx89/pydicom-seg.git\ncd pydicom-seg\npoetry build\npip install dist/pydicom_seg-<version>-py3-none-any.whl\n```\n\n### Development\n\nAfter cloning the repository, please install the git `pre-commit` hook to\nenforce code style and run static code analysis on every git commit.\n\n```bash\ngit clone \\\n    --recurse-submodules \\\n    https://github.com/razorx89/pydicom-seg.git\ncd pydicom-seg\npoetry install\npoetry run pre-commit install\n```\n\n## Getting Started\n\n### Loading binary segments\n\n```python\nimport pydicom\nimport pydicom_seg\nimport SimpleITK as sitk\n\ndcm = pydicom.dcmread('segmentation.dcm')\n\nreader = pydicom_seg.SegmentReader()\nresult = reader.read(dcm)\n\nfor segment_number in result.available_segments:\n    image_data = result.segment_data(segment_number)  # directly available\n    image = result.segment_image(segment_number)  # lazy construction\n    sitk.WriteImage(image, f'/tmp/segmentation-{segment_number}.nrrd', True)\n```\n\n### Loading a multi-class segmentation\n\n```python\ndcm = pydicom.dcmread('segmentation.dcm')\n\nreader = pydicom_seg.MultiClassReader()\nresult = reader.read(dcm)\n\nimage_data = result.data  # directly available\nimage = result.image  # lazy construction\nsitk.WriteImage(image, '/tmp/segmentation.nrrd', True)\n```\n\n### Saving a multi-class segmentation\n\nPlease generate a `metainfo.json` for the segments you want to serialize using the\n[web-based editor from dcmqi](http://qiicr.org/dcmqi/#/seg).\n\n```python\nsegmentation: SimpleITK.Image = ...  # A segmentation image with integer data type\n                                     # and a single component per voxel\ndicom_series_paths = [...]  # Paths to an imaging series related to the segmentation\nsource_images = [\n    pydicom.dcmread(x, stop_before_pixels=True)\n    for x in dicom_series_paths\n]\ntemplate = pydicom_seg.template.from_dcmqi_metainfo('metainfo.json')\nwriter = pydicom_seg.MultiClassWriter(\n    template=template,\n    inplane_cropping=False,  # Crop image slices to the minimum bounding box on\n                             # x and y axes. Maybe not supported by other frameworks.\n    skip_empty_slices=True,  # Don't encode slices with only zeros\n    skip_missing_segment=False,  # If a segment definition is missing in the\n                                 # template, then raise an error instead of\n                                 # skipping it.\n)\ndcm = writer.write(segmentation, source_images)\ndcm.save_as('segmentation.dcm')\n```\n\n## License\n\n`pydicom-seg` is distributed under the [MIT license](./LICENSE).\n",
    'author': 'Sven Koitka',
    'author_email': 'sven.koitka@uk-essen.de',
    'maintainer': None,
    'maintainer_email': None,
    'url': 'https://github.com/razorx89/pydicom-seg',
    'packages': packages,
    'package_data': package_data,
    'install_requires': install_requires,
    'python_requires': '>=3.6.1,<4.0.0',
}


setup(**setup_kwargs)
