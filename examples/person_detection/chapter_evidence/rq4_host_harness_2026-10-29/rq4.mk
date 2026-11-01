RQ4_SRCS := $(TENSORFLOW_ROOT)tensorflow/lite/micro/examples/rq4_host/rq4_host_main.cc \
            $(TENSORFLOW_ROOT)tensorflow/lite/micro/examples/rq1_arm/rq1_data.cc
RQ4_HDRS := $(TENSORFLOW_ROOT)tensorflow/lite/micro/examples/rq1_arm/rq1_data.h \
            $(TENSORFLOW_ROOT)tensorflow/lite/micro/examples/rq4_host/rq4_expected.h
$(eval $(call microlite_test,rq4_host_kat,$(RQ4_SRCS),$(RQ4_HDRS),))
