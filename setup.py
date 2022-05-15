from setuptools import setup, find_packages
from pkg_resources import DistributionNotFound, get_distribution

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

ALT_OPENCV = (
    "opencv-contrib-python",
    "opencv-contrib-python-headless",
    "opencv-python",
)

opencv_install = "opencv-python-headless"
for alt in ALT_OPENCV:
    try:
        get_distribution(alt)
        opencv_install = alt
        break
    except DistributionNotFound:
        print(alt + " not found!")
        pass
print(opencv_install + " chosen")

setup(
    name="deep-sort-realtime",
    version="1.2",
    author="levan92",
    author_email="lingevan0208@gmail.com",
    description="A more realtime adaptation of Deep SORT",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/levan92/deep_sort_realtime",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    packages=find_packages(exclude=("test",)),
    package_data={
        "deep_sort_realtime.embedder": [
            "weights/mobilenetv2_bottleneck_wts.pt",
            "weights/download_clip_wts.sh",
            "weights/download_tf_wts.sh",
        ]
    },
    install_requires=["numpy", "scipy", opencv_install],
)
