# -*- coding: utf-8 -*-
"""EAST_TFLite

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/github/sayakpaul/Adventures-in-TensorFlow-Lite/blob/master/EAST_TFLite.ipynb

This notebook relies on this PyImageSearch blog post [OpenCV Text Detection (EAST text detector)](https://www.pyimagesearch.com/2018/08/20/opencv-text-detection-east-text-detector/) to convert a pre-trained EAST model to TFLite.

From the blog post:
> The EAST pipeline is capable of predicting words and lines of text at arbitrary orientations on 720p images, and furthermore, can run at 13 FPS, according to the authors.

EAST was proposed in [An Efficient and Accurate Scene Text Detector](https://arxiv.org/abs/1704.03155).

## Setup
"""

import tensorflow as tf
tf.__version__

"""## Executing the code from the blog post

We will be first executing the original codebase to just have a test of the results.
"""

!wget http://t.dripemail2.com/c/eyJhY2NvdW50X2lkIjoiNDc2ODQyOSIsImRlbGl2ZXJ5X2lkIjoiYnFoc2xnandzMWtteWw5M3NkeTAiLCJ1cmwiOiJodHRwOi8vcHlpbWcuY28vZHM1c2k_X19zPXp3a2NncTN3aG5oemhleDJ1ZHJmIn0

!unzip eyJhY2NvdW50X2lkIjoiNDc2ODQyOSIsImRlbGl2ZXJ5X2lkIjoiYnFoc2xnandzMWtteWw5M3NkeTAiLCJ1cmwiOiJodHRwOi8vcHlpbWcuY28vZHM1c2k_X19zPXp3a2NncTN3aG5oemhleDJ1ZHJmIn0

!python /content/opencv-text-detection/text_detection.py --image /content/opencv-text-detection/images/lebron_james.jpg \
	--east /content/opencv-text-detection/frozen_east_text_detection.pb

"""Be sure to comment out the last two lines of `text_detection.py` script and add `cv2.imwrite("image.png", orig)`. After you are done executing the script see the result by opening "image.png".

## TFLite model conversion

If we export the float16 model with a fixed known input shape we can can likely accelerate its inference with TFLite GPU delegate. We can specify the `input_shapes` argument in the `tf.compat.v1.lite.TFLiteConverter.from_frozen_graph()` function to do this. We are going to follow this same principle for other quantization (i.e. int8 and dynamic-range) methods as well.
"""

import os
import cv2
import numpy as np

IMG_SIZE = 320
images_list = os.listdir('/content/opencv-text-detection/images')

# int8 quantization requires a representative dataset generator
def representative_dataset_gen():
    for image_path in images_list:
        image = cv2.imread(os.path.join('/content/opencv-text-detection/images', image_path))
        image = cv2.resize(image, (IMG_SIZE, IMG_SIZE))
        image = image.astype("float32")
        mean = np.array([123.68, 116.779, 103.939][::-1], dtype="float32")
        image -= mean
        image = np.expand_dims(image, axis=0)
        yield [image]

quantization = "float16" #@param ["dr", "int8", "float16"]
converter = tf.compat.v1.lite.TFLiteConverter.from_frozen_graph(
    graph_def_file='/content/opencv-text-detection/frozen_east_text_detection.pb', 
    input_arrays=['input_images'],
    output_arrays=['feature_fusion/Conv_7/Sigmoid', 'feature_fusion/concat_3'],
    input_shapes={'input_images': [1, 320, 320, 3]}
)

converter.optimizations = [tf.lite.Optimize.DEFAULT]

if quantization=="float16":
    converter.target_spec.supported_types = [tf.float16]
elif quantization=="int8":
    # converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.representative_dataset = representative_dataset_gen
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    # converter.inference_input_type = tf.uint8
    # converter.inference_output_type = tf.uint8

tflite_model = converter.convert()

with open('east_text_detection_320x320_float16_quant.tflite', 'wb') as w:
    w.write(tflite_model)

!ls -l

"""From the blog post:

```
# define the two output layer names for the EAST detector model that
# we are interested -- the first is the output probabilities and the
# second can be used to derive the bounding box coordinates of text
layerNames = [
	"feature_fusion/Conv_7/Sigmoid",
	"feature_fusion/concat_3"]
```
"""

open('east_model_{}.tflite'.format(quantization), 'wb').write(tflite_model)

!ls -lh east_model_{quantization}.tflite

!ls -lh /content/opencv-text-detection/frozen_east_text_detection.pb

"""## Inference"""

from imutils.object_detection import non_max_suppression
import numpy as np
import time
import cv2

"""### Prepare an input image"""

# load the input image and grab the image dimensions
image = cv2.imread("/content/opencv-text-detection/images/lebron_james.jpg")
orig = image.copy()
(H, W) = image.shape[:2]
print(H, W)

# set the new width and height and then determine the ratio in change
# for both the width and height
(newW, newH) = (320, 320)
rW = W / float(newW)
rH = H / float(newH)

# resize the image and grab the new image dimensions
image = cv2.resize(image, (newW, newH))
(H, W) = image.shape[:2]
print(H, W)

# convert the image to a floating point data type and perform mean
# subtraction
image = image.astype("float32")
mean = np.array([123.68, 116.779, 103.939][::-1], dtype="float32")
image -= mean
image = np.expand_dims(image, 0)

"""### Perform inference"""

quantization = "float16" #@param ["dr", "int8", "float16"]
interpreter = tf.lite.Interpreter(model_path=f'east_model_{quantization}.tflite')
input_details = interpreter.get_input_details()

# if quantization != "float16":
#     interpreter.resize_tensor_input(0, [1, image.shape[1], image.shape[2], 3]) 

interpreter.allocate_tensors()
interpreter.set_tensor(input_details[0]['index'], image)
start = time.time()
interpreter.invoke()
print(f"Inference took: {time.time()-start} seconds")

# Investigate the output
interpreter.get_output_details()

# Parse the outputs
scores = interpreter.tensor(
    interpreter.get_output_details()[0]['index'])()
geometry = interpreter.tensor(
    interpreter.get_output_details()[1]['index'])()

# We need to have this shape:  (1, 1, 80, 80) (1, 5, 80, 80) 
scores.shape, geometry.shape

scores = np.transpose(scores, (0, 3, 1, 2)) 
geometry = np.transpose(geometry, (0, 3, 1, 2))
scores.shape, geometry.shape

"""## Processing the inference results

Note that majority of the following section comes from the blog post I mentioned at the beginning.
"""

from google.colab.patches import cv2_imshow

# grab the number of rows and columns from the scores volume, then
# initialize our set of bounding box rectangles and corresponding
# confidence scores
(numRows, numCols) = scores.shape[2:4]
rects = []
confidences = []

# loop over the number of rows
for y in range(0, numRows):
	# extract the scores (probabilities), followed by the geometrical
	# data used to derive potential bounding box coordinates that
	# surround text
	scoresData = scores[0, 0, y]
	xData0 = geometry[0, 0, y]
	xData1 = geometry[0, 1, y]
	xData2 = geometry[0, 2, y]
	xData3 = geometry[0, 3, y]
	anglesData = geometry[0, 4, y]

	# loop over the number of columns
	for x in range(0, numCols):
		# if our score does not have sufficient probability, ignore it
		if scoresData[x] < 0.5:
			continue

		# compute the offset factor as our resulting feature maps will
		# be 4x smaller than the input image
		(offsetX, offsetY) = (x * 4.0, y * 4.0)

		# extract the rotation angle for the prediction and then
		# compute the sin and cosine
		angle = anglesData[x]
		cos = np.cos(angle)
		sin = np.sin(angle)

		# use the geometry volume to derive the width and height of
		# the bounding box
		h = xData0[x] + xData2[x]
		w = xData1[x] + xData3[x]

		# compute both the starting and ending (x, y)-coordinates for
		# the text prediction bounding box
		endX = int(offsetX + (cos * xData1[x]) + (sin * xData2[x]))
		endY = int(offsetY - (sin * xData1[x]) + (cos * xData2[x]))
		startX = int(endX - w)
		startY = int(endY - h)

		# add the bounding box coordinates and probability score to
		# our respective lists
		rects.append((startX, startY, endX, endY))
		confidences.append(scoresData[x])

# apply non-maxima suppression to suppress weak, overlapping bounding
# boxes
boxes = non_max_suppression(np.array(rects), probs=confidences)

# loop over the bounding boxes
for (startX, startY, endX, endY) in boxes:
	# scale the bounding box coordinates based on the respective
	# ratios
	startX = int(startX * rW)
	startY = int(startY * rH)
	endX = int(endX * rW)
	endY = int(endY * rH)

	# draw the bounding box on the image
	cv2.rectangle(orig, (startX, startY), (endX, endY), (0, 255, 0), 2)

# show the output image
cv2_imshow(orig)

"""One can utilize [this script](https://gist.github.com/sayakpaul/24314074d16018c1ce1b7699cc8395ab#file-text_detection_video-py) and perform real-time text detection. 

Results on my humble MacBook Air (13-inch, 2017) (Processor: 1.8 GHz Intel Core i5) (Memory: 8 GB 1600 MHz DDR3):

```shell
$ text_detection_video.py --east east_model_float16.tflite
[INFO] starting video stream...
[INFO] elasped time: 73.27
[INFO] approx. FPS: 1.17
```

**Other details**: 
- **TensorFlow version**: 2.3.0 
- **Model**:  [float16](https://github.com/sayakpaul/Adventures-in-TensorFlow-Lite/releases/download/v0.6.0/east_model_float16.tar.gz)

A demo of the real-time results is available [here](https://youtu.be/CpywwaAmHPs). 

To actually perform OCR, one can further process these results with a library like `pytesseract`. Refer to [this blog post](https://www.pyimagesearch.com/2018/09/17/opencv-ocr-and-text-recognition-with-tesseract/) if you want to do it right away.
"""