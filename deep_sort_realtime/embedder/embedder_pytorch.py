import os
import logging

import cv2
import numpy as np
import pkg_resources
import torch
import torch.jit
from torchvision.transforms import transforms

from deep_sort_realtime.embedder.mobilenetv2_bottle import MobileNetV2_bottle

logger = logging.getLogger(__name__)

MOBILENETV2_BOTTLENECK_WTS = pkg_resources.resource_filename(
    "deep_sort_realtime", "embedder/weights/mobilenetv2_bottleneck_wts.pt"
)
INPUT_WIDTH = 224


def batch(iterable, bs=1):
    l = len(iterable)
    for ndx in range(0, l, bs):
        yield iterable[ndx: min(ndx + bs, l)]


class MobileNetv2_Embedder(object):
    """
    MobileNetv2_Embedder loads a Mobilenetv2 pretrained on Imagenet1000, with classification layer removed, exposing the bottleneck layer, outputing a feature of size 1280.

    Params
    ------
    - model_wts_path (optional, str) : path to mobilenetv2 model weights, defaults to the model file in ./mobilenetv2
    - half (optional, Bool) : boolean flag to use half precision or not, defaults to True
    - max_batch_size (optional, int) : max batch size for embedder, defaults to 16
    - bgr (optional, Bool) : boolean flag indicating if input frames are bgr or not, defaults to True
    - gpu (optional, Bool) : boolean flag indicating if gpu is enabled or not
    """

    def __init__(
        self, model_wts_path=None, half=True, max_batch_size=16, bgr=True, gpu=True
    ):
        if model_wts_path is None:
            model_wts_path = MOBILENETV2_BOTTLENECK_WTS
        assert os.path.exists(
            model_wts_path
        ), f"Mobilenetv2 model path {model_wts_path} does not exists!"
        self.model = MobileNetV2_bottle(input_size=INPUT_WIDTH, width_mult=1.0)
        self.model.load_state_dict(torch.load(model_wts_path))

        self.gpu = gpu
        if self.gpu:
            self.model.cuda()  # loads model to gpu
            self.half = half
            if self.half:
                self.model.half()
        else:
            self.half = False

        self.model.eval()  # inference mode, deactivates dropout layers

        self.max_batch_size = max_batch_size
        self.bgr = bgr

        # tracing produces simpler code than scripting at lost of control flow
        # model is simplistic & doesnt contain control flow so this is fine
        # https://nvidia.github.io/Torch-TensorRT/tutorials/creating_torchscript_module_in_python.html#working-with-torchscript-in-python
        # torch-tensorrt optimizes traced modules better
        # eventually will test using tensorrt for even more performance
        self.model = torch.jit.trace(
            self.model, torch.zeros((self.max_batch_size, 3, INPUT_WIDTH, INPUT_WIDTH), dtype=torch.float16, device='cuda'))

        logger.info("MobileNetV2 Embedder for Deep Sort initialised")
        logger.info(f"- gpu enabled: {self.gpu}")
        logger.info(f"- half precision: {self.half}")
        logger.info(f"- max batch size: {self.max_batch_size}")
        logger.info(f"- expects BGR: {self.bgr}")

        zeros = np.zeros((100, 100, 3), dtype=np.uint8)
        self.predict([zeros])  # warmup

    def preprocess(self, np_image):
        """
        Preprocessing for embedder network: Flips BGR to RGB, resize, convert to torch tensor, normalise with imagenet mean and variance, reshape. Note: input image yet to be loaded to GPU through tensor.cuda()

        Parameters
        ----------
        np_image : ndarray
            (H x W x C)

        Returns
        -------
        Torch Tensor

        """
        if self.bgr:
            np_image_rgb = np_image[..., ::-1]
        else:
            np_image_rgb = np_image

        input_image = cv2.resize(np_image_rgb, (INPUT_WIDTH, INPUT_WIDTH))
        trans = transforms.Compose(
            [
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]
                ),
            ]
        )
        input_image = trans(input_image)
        input_image = input_image.view(1, 3, INPUT_WIDTH, INPUT_WIDTH)

        return input_image

    def predict(self, np_images):
        """
        batch inference

        Params
        ------
        np_images : list of ndarray
            list of (H x W x C), bgr or rgb according to self.bgr

        Returns
        ------
        list of features (np.array with dim = 1280)

        """
        all_feats = []

        preproc_imgs = [self.preprocess(img) for img in np_images]

        for this_batch in batch(preproc_imgs, bs=self.max_batch_size):
            this_batch = torch.cat(this_batch, dim=0)
            if self.gpu:
                this_batch = this_batch.cuda()
                if self.half:
                    this_batch = this_batch.half()
            output = self.model.forward(this_batch)

            all_feats.extend(output.cpu().data.numpy())

        return all_feats
