#!/bin/sh
#
# Copyright 2015-present Facebook. All Rights Reserved.
#
# This program file is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program in a file named COPYING; if not, write to the
# Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor,
# Boston, MA 02110-1301 USA
#
PWM_DIR=/sys/devices/platform/ast_pwm_tacho.0
TACH_BUS=5
TACH_ADDR=0x2d
TACH_REGISTER_L=0x24
TACH_REGISTER_H=0x25

set -e

# The PWM frequency is

#   clk_source / ((2 ^ division_) * (2 * division_l) * (unit + 1))
#
# Our clk_source is 24Mhz.  4-pin fans are generally supposed to be driven with
# a 25Khz PWM control signal.  Therefore we want the divisor to equal 960.
#
# We also want the unit to be as large as possible, since this controls the
# granularity with which we can modulate the PWM signal.  The following
# settings allow us to set the fan from 0 to 100% in increments of 1/96th.
#
# The AST chip supports 3 different PWM clock configurations, but we only use
# type M for now.
echo 0 > $PWM_DIR/pwm_type_m_division_h
echo 5 > $PWM_DIR/pwm_type_m_division_l
echo 95 > $PWM_DIR/pwm_type_m_unit

# On Lightning, there are 6 fans which are driven by Tacho0.
# Each fan uses same PWM input and provide one tacho output.
# Here is the mapping between the fan and PWN/Tacho,
# staring from the one from the edge
# Fan 0: PWM 0, Tacho0

# For each fan, setting the type, and 100% initially
echo 0 > $PWM_DIR/pwm0_type
echo 0 > $PWM_DIR/pwm0_rising
echo 0 > $PWM_DIR/pwm0_falling
echo 1 > $PWM_DIR/pwm0_en

# Enable Tach 0
i2cset -y $TACH_BUS $TACH_ADDR $TACH_REGISTER_L 0xFF b
i2cset -y $TACH_BUS $TACH_ADDR $TACH_REGISTER_H 0x0F b
