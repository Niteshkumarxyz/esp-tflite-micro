idf_component_register(
    SRCS "rq4_main.cc"
         "../../person_detection/main/person_detect_model_data.cc"
    INCLUDE_DIRS "." "../../person_detection/main"
    PRIV_REQUIRES static_images esp_timer app_update esp_partition esp_app_format spi_flash)
