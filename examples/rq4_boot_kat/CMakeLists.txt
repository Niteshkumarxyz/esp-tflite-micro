# RQ4 boot-time acceptance test for the person_detection model (W1).
# Reuses the person_detection model data and its 12 static images; nothing in that example is changed.
cmake_minimum_required(VERSION 3.16)

set(EXTRA_COMPONENT_DIRS "${CMAKE_CURRENT_LIST_DIR}/../person_detection/static_images")
include($ENV{IDF_PATH}/tools/cmake/project.cmake)

# Positive-control build: pass -D RQ4_SINGLE_ROUNDING=1 to idf.py. It switches TFLM's
# fixed-point requantization to its documented single-rounding variant in every component.
if(RQ4_SINGLE_ROUNDING)
    idf_build_set_property(COMPILE_DEFINITIONS "TFLITE_SINGLE_ROUNDING=1" APPEND)
    message(STATUS "RQ4: TFLITE_SINGLE_ROUNDING=1 (positive-control build)")
endif()

project(rq4_boot_kat)
