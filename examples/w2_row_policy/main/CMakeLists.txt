idf_component_register(
    SRCS "main.cc" "w2_models.cc"
    PRIV_REQUIRES esp_driver_uart esp_app_format esp_timer
    INCLUDE_DIRS "")
