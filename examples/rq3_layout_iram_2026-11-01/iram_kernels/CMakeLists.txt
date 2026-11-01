# Carries only a linker fragment that moves ESP-NN's optimized convolution and depthwise convolution
# objects from flash to IRAM. Added to a build only when the project is configured with -D IRAM_KERNELS=1.
idf_component_register(SRCS "iram_kernels.c"
                       LDFRAGMENTS "linker.lf")
