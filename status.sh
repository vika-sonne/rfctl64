#!/usr/bin/env sh

lsmod|grep rfctl
is_kernel_module_loaded=$?

exit $is_kernel_module_loaded
