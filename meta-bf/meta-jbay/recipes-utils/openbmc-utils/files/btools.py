#!/usr/bin/python
#
# File is the tool for bringup of tofino chipset on Jbay.
#
import sys
import os
import getopt
import subprocess
import os.path
from time import sleep

#
# btool usage for modules. Individual module usage is printed separately
#
def usage():

    print " "
    print "USAGE: "
    print "./btools.py --<[device]/help>"
    print "[device]"
    print "          PSU  => PFE1100 power supply unit"
    print "          UCD  => UCD90120A power supply sequencer"
    print "          IR   => Multiphase Controller"
    print "          TMP  => Temperature Sensors"
    print "Eg:"
    print "./btools.py --PSU help"
    print "./btools.py --UCD help"
    print "./btools.py --IR help"
    print "./btools.py --help"

    return
#
# Usage for PSU related arguments
#
def error_psu_usage():
    print " "
    print "USAGE: "
    print "./btools.py --PSU <power supply number> r v              => input voltage"
    print "                     <1 - 2>            r vo             => output voltage"
    print "                                        r i              => current"
    print "                                        r p              => power"
    print "                                        r ld             => load sharing"
    print "                                        r fspeed         => fan speed"
    print "                                        r ffault         => fan fault"
    print "                                        r presence       => power supply presence"
    print "                                        r sts_in_power   => power input status"
    print "                                        r sts_op_power   => power output status"
    print " "
    print "./btools.py --PSU 1 r v   => Read input voltage for power supply 1"

#
# Presence and power status is read from CPLD
#
def psu_cpld_features(power_supply, feature):

    cpld_dev = "/sys/class/i2c-adapter/i2c-12/12-0031/"
    cmd = "cat"

    if feature == "presence":
        if power_supply == 1:
            path = cpld_dev + "psu1_present"
        elif power_supply == 2:
            path = cpld_dev + "psu2_present"
        else:
            error_psu_usage()
            return
    elif feature == "sts_in_power":
        if power_supply == 1:
            path = cpld_dev + "psu1_in_pwr_sts"
        elif power_supply == 2:
            path = cpld_dev + "psu2_in_pwr_sts"
        else:
            error_psu_usage()
            return
    elif feature == "sts_op_power":
        if power_supply == 1:
            path = cpld_dev + "psu1_output_pwr_sts"
        elif power_supply == 2:
            path = cpld_dev + "psu2_output_pwr_sts"
        else:
            error_psu_usage()
            return
    else:
        error_psu_usage()
        return

    try:
        output = subprocess.check_output([cmd, path])
    except subprocess.CalledProcessError as e:
        print e
        print "Error while executing psu cpld feature commands"
        return

    if feature == "presence":
        res = int(output, 16)
        if res == 0:
            print "Power supply %s present" % power_supply
            return 0
        else:
            print "Power supply %s not present" % power_supply
            return 1
    elif feature == "sts_in_power" or feature == "sts_op_power":
        # catching only first 3 characters of output
        res = int(output[:3], 16)
        if res == 0:
            print "Power supply status: BAD"
        elif res == 1:
            print "Power supply status: OK"
        else:
            print "Error while reading power supply status"
    return

#
# Function reads power supplies output voltage
#
def psu_read_output_voltage(power_supply):

    PSU_I2C_BUS = "7"
    PSU_I2C_READ_VOUT = "0x8b"

    if power_supply == 1:
        PSU_I2C_ADDR = "0x5a"
    else:
        PSU_I2C_ADDR = "0x59"

    try:
        get_cmd = "i2cget"
        output = subprocess.check_output([get_cmd, "-f", "-y", PSU_I2C_BUS,
                                     PSU_I2C_ADDR, PSU_I2C_READ_VOUT, "w"])
    except subprocess.CalledProcessError as e:
        print e
        print "Error occured while processing output for PSU %d " % power_supply
        return

    # From PFE specs READ_VOUT1
    PSU_VOLTAGE_LN_FMT = 0x1 << 6

    # 11 bits are usable
    output = int(output, 16) & 0x7ff

    output = float(output) / PSU_VOLTAGE_LN_FMT

    print "Output Voltage  %.1fV" % output

    return

#
# Function is retrive current withdrawn on both power supplies
#
def psu_read_load_sharing():

    PSU_I2C_BUS = "7"
    PSU_I2C_READ_IOUT = "0x8C"

    try:
        #Read 1st power supply
        PSU_I2C_ADDR = "0x5a"
        get_cmd = "i2cget"
        output1 = subprocess.check_output([get_cmd, "-f", "-y", PSU_I2C_BUS,
                                          PSU_I2C_ADDR, PSU_I2C_READ_IOUT, "w"])

        PSU_I2C_ADDR = "0x59"
        output2 = subprocess.check_output([get_cmd, "-f", "-y", PSU_I2C_BUS,
                                          PSU_I2C_ADDR, PSU_I2C_READ_IOUT, "w"])

    except subprocess.CalledProcessError as e:
        print e
        print "Error occured while processing load sharing for PSU"
        return

    # From PFE specs READ_IOUT1
    PSU_CURRENT_LN_FMT = 0x1 << 3

    # 11 bits are usable
    output1 = int(output1, 16) & 0x7ff
    output1 = float(output1) / PSU_CURRENT_LN_FMT

    output2 = int(output2, 16) & 0x7ff
    output2 = float(output2) / PSU_CURRENT_LN_FMT

    print "Power Supply 1 output current  %.3f amp" % output1
    print "Power Supply 2 output current  %.3f amp" % output2

    return

#
#open I2C sw before pfe devices and then load drivers
#
def psu_init():

    #check if pfe1100 driver is loaded properly
    if os.path.isfile("/sys/class/i2c-adapter/i2c-7/7-0059/in1_input") \
       and os.path.isfile("/sys/class/i2c-adapter/i2c-7/7-005a/in1_input"):
        return

    try:
        cmd = "i2cset"
        I2C_ADDR = "0x70"
        I2C_BUS = "7"
        OPCODE = "0x3"

        # Open I2C swtich for PFE devices
        #i2cset -f -y 7 0x70 0x3
        subprocess.check_output([cmd, "-f", "-y", I2C_BUS, I2C_ADDR, OPCODE])
        
	# load driver for both devices
        o = subprocess.check_output(["lsmod", "pfe1100"])

	if len(o) != 0:
            # load driver for both devices
            subprocess.check_output(["rmmod", "pfe1100"])

        # load driver for both devices
        subprocess.check_output(["modprobe", "pfe1100"])

    except subprocess.CalledProcessError as e:
        print e
        print "Error occured while initializing PSU"
        return

#function just for power supply check
def psu_check_pwr_presence(power_supply):

  psu_init()

  r = psu_cpld_features(power_supply, "presence")

  return r

#
# Function to handle PSU related requests
#
def psu(argv):

    i2c_dev = "/sys/class/i2c-adapter/i2c-7/7-00"

    arg_psu = argv[2:]

    if arg_psu[0] == "help" or arg_psu[0] == "h":
        error_psu_usage()
        return

    if arg_psu[0] != "1" and arg_psu[0] != "2":
        error_psu_usage()
        return

    psu_init()

    # Mapping i2c bus address according to power supply number
    # 2018.09.10 Swap PSUs mapping because of reverse.
    if arg_psu[0] == "1":
        power_supply = 1
        ps = "5a/"
    elif arg_psu[0] == "2":
        power_supply = 2
        ps = "59/"

    if arg_psu[1] == "r":
        cmd = "cat"
    else:
        error_psu_usage()
        return

    if arg_psu[2] == "v":
        val = "in1_input"
        s = "V"
    elif arg_psu[2] == "i":
        val = "curr1_input"
        s = "mA"
    elif arg_psu[2] == "p":
        val = "power1_input"
        s = "mW"
    elif arg_psu[2] == "fspeed":
        val = "fan1_input"
        s = "rpm"
    elif arg_psu[2] == "ffault":
        val = "fan1_fault"
        s = "ffault"
    elif arg_psu[2] == "presence":
        psu_cpld_features(power_supply, "presence")
        return
    elif arg_psu[2] == "sts_in_power":
        psu_cpld_features(power_supply, "sts_in_power")
        return
    elif arg_psu[2] == "sts_op_power":
        psu_cpld_features(power_supply, "sts_op_power")
        return
    elif arg_psu[2] == "vo":
        psu_read_output_voltage(power_supply)
        return
    elif arg_psu[2] == "ld":
        psu_read_load_sharing()
        return
    elif arg_psu[2] == "psmodel":
        val = "mfr_model_label"
        s = "model"
    elif arg_psu[2] == "psserial":
        val = "mfr_serial_label"
        s = "serial"
    elif arg_psu[2] == "psrev":
        val = "mfr_revision_label"
        s = "rev"
    else:
        error_psu_usage()
        return

    path = i2c_dev + ps + val

    try:
        I2C_ADDR = "0x70"
        I2C_BUS = "7"
        OPCODE = "0x3"

        # Force Open I2C swtich for PFE devices. Facebook psu mon messes up i2c mux
        #i2cset -f -y 7 0x70 0x3
        subprocess.check_output(["i2cset", "-f", "-y", I2C_BUS, I2C_ADDR, OPCODE])


        output = subprocess.check_output([cmd, path])
    except subprocess.CalledProcessError as e:
        print e
        print "Error while executing psu i2c command "
        return

    if s == "V":
        print "{}{}".format(float(output) / 1000, "V")             # convert milli volts to volts
    elif s == "mA":
        print "{}{}".format(float(output), "mA")                   # current is in milli Amperes
    elif s == "mW":
        print "{}{}".format(float(output) / 1000 , "mW")           # Power in milli watts
    elif s == "rpm":
        print "{}{}".format(int(output), "rpm")                    # Speed of FAN
    elif s == "ffault":
        print "{}".format(int(output))
    elif s == "model":
        print "{}".format(output)
    elif s == "serial":
        print "{}".format(output)
    elif s == "rev":
        print "{}".format(output)
    return

#
# Usage for UCD device
#
def error_ucd_usage():

    print " "
    print "Usage:"
    print "./btools.py --UCD sh v <jbay>    => Show Voltage of all rails"
    print "                  fault    => Show Voltage fault/warnings of all rails"
    print "                  set_margin  <rail number> <margin> <jbay>"
    print "                                 <1 - 12>    l /h /n"
    print "                                             l => low"
    print "                                             h => high"
    print "                                             n => none"

    print "./btools.py --UCD sh v jbay"
    print "./btools.py --UCD set_margin 5 l jbay"
    print " "

#
# Reads voltage faults on all rails
#
def ucd_rail_voltage_fault():

    i = 1

    UCD_I2C_BUS = "2"
    UCD_I2C_ADDR = "0x34"
    UCD_STATUS_VOUT_OP = "0x7A"
    UCD_PAGE_OP = "0x00"

    print " "
    print " RAIL      Voltage Warnings"

    # Parse 1 to 12 voltage rails
    for i in range(0, 12):

        try:
            # i2cset -f -y 2 0x34 0x00 i
            set_cmd = "i2cset"
            output = subprocess.check_output([set_cmd, "-f", "-y", UCD_I2C_BUS,
                                     UCD_I2C_ADDR, UCD_PAGE_OP, str(hex(i))])
        except subprocess.CalledProcessError as e:
            print e
            print "Error occured while processing i2cset for rail %.2d " % i
            continue

        try:
            # i2cget -f -y 2 0x34 w
            get_cmd = "i2cget"
            output = subprocess.check_output([get_cmd, "-f", "-y", UCD_I2C_BUS,
                                               UCD_I2C_ADDR, UCD_STATUS_VOUT_OP])

        except subprocess.CalledProcessError as e:
            print e
            print "Error occured while processing i2cget for rail %.2d " % i
            continue


        o = int(output, 16)

        fault_warnings = ""

        if o == 0:
            fault_warnings = "No fault/warning"
        else:
            if o & 0x10:
                fault_warnings = fault_warnings + "Under Voltage Fault,"

            if o & 0x20:
                fault_warnings = fault_warnings + "Under Voltage Warning,"

            if o & 0x40:
                fault_warnings = fault_warnings + "Over Voltage Warning,"

            if o & 0x80:
                fault_warnings = fault_warnings + "Over Voltage Fault,"

        print "  %.2d         %s" % (i + 1, fault_warnings)

    print " "

    return


#
# Displays all rails voltages jbay
#
def ucd_rail_voltage_jbay():

    i = 1

    UCD_I2C_BUS = "2"
    UCD_I2C_ADDR = "0x34"
    UCD_READ_OP = "0x8b"
    UCD_PAGE_OP = "0x00"
    UCD_VOUT_MODE_OP = "0x20"

    print " "
    print " RAIL                          Voltage(V)"

    string = {1: "01-  VDD12V", 2: "02-  VDD5V_stby", 3: "03-  VDD3_3V_iso",
	      4: "04*- VDD3_3V", 5: "05-  VDD3_3V_stby", 6: "06-  VDD2_5V_stby",
              7: "07-  VDD2_5V_tf", 8: "08-  VDD1_8V_stby", 9: "09-  VDD1_5V_stby",
              10: "10-  VDD1_2V_stby", 11: "11*-  VDD0_9V_anlg", 12: "12*-  VDD_core"}

# Parse 1 to 12 voltage rails
    for i in range(0, 12):

        try:
            # i2cset -f -y 2 0x34 0x00 i
            set_cmd = "i2cset"
            output = subprocess.check_output([set_cmd, "-f", "-y", UCD_I2C_BUS,
                                     UCD_I2C_ADDR, UCD_PAGE_OP, str(hex(i))])
        except subprocess.CalledProcessError as e:
            print e
            print "Error occured while processing i2cset for rail %.2d " % i
            continue

        try:
            # i2cget -f -y 2 0x34 w
            get_cmd = "i2cget"
            mantissa = subprocess.check_output([get_cmd, "-f", "-y", UCD_I2C_BUS,
                                               UCD_I2C_ADDR, UCD_READ_OP, "w"])

        except subprocess.CalledProcessError as e:
            print e
            print "Error occured while processing i2cget for rail %.2d " % i
            continue

        try:
            # i2cget -f -y 2 0x34 0x20
            get_cmd = "i2cget"
            exponent = subprocess.check_output([get_cmd, "-f", "-y", UCD_I2C_BUS,
                                               UCD_I2C_ADDR, UCD_VOUT_MODE_OP])
        except subprocess.CalledProcessError as e:
            print e
            print "Error occured while processing i2cget for rail %.2d " % i
            continue

        # 2 ^ exponent
        # exponent is 5 bit signed value. Thus calculating first exponent.
        # It is based on UCD90120A device spec section 2.2
        exp = int(exponent, 16) | ~0x1f
        exp = ~exp + 1
        div = 1 << exp

        mantissa = int(mantissa, 16)

        print "  %-*s          %.3f" % (20, string.get(i + 1), float(mantissa) / float(div))

    print "  "
    print "* voltages can be margined by IR CLI only "
    print "  "

    return

#
# Functions set the voltage margins
#
def ucd_voltage_margin(arg):

    UCD_I2C_BUS = "2"
    UCD_I2C_ADDR = "0x34"
    UCD_LOW_MARGIN_OP = "0x18"
    UCD_HIGH_MARGIN_OP = "0x28"
    UCD_NONE_MARGIN_OP = "0x08"
    UCD_PAGE_OP = "0x00"
    UCD_MARGIN_OP = "0x01"

    if len(arg) is not 4:
        error_ucd_usage()
        return
    elif arg[3] == "jbay":
    	if not 1 <= int(arg[1]) <= 12:
             error_ucd_usage()
             return
    else:
        error_ucd_usage()
        return

    if arg[2] == "l":
        opcode = str(UCD_LOW_MARGIN_OP)
    elif arg[2] == "h":
        opcode = str(UCD_HIGH_MARGIN_OP)
    elif arg[2] == "n":
        opcode = str(UCD_NONE_MARGIN_OP)
    else:
        error_ucd_usage()
        return


    # Rail number mapping starts from 1
    # But UCD understand from 0. Thus reducing 1
    rail_number = int(arg[1]) - 1

    try:

        set_cmd = "i2cset"
        output = subprocess.check_output([set_cmd, "-f", "-y", UCD_I2C_BUS,
                                         UCD_I2C_ADDR, UCD_PAGE_OP, str(rail_number)])

    except subprocess.CalledProcessError as e:
        print e
        print "Error occured while processing i2cset for rail %.2d " % (rail_number + 1)
        return

    try:

        set_cmd = "i2cset"
        output = subprocess.check_output([set_cmd, "-f", "-y", UCD_I2C_BUS,
                                         UCD_I2C_ADDR, UCD_MARGIN_OP, opcode])
    except subprocess.CalledProcessError as e:
        print e
        print "Error occured while processing i2cset for rail %.2d " % (rail_number + 1)
        return

    try:

        set_cmd = "i2cget"
        output = subprocess.check_output([set_cmd, "-f", "-y", UCD_I2C_BUS,
                                         UCD_I2C_ADDR, UCD_MARGIN_OP])

    except subprocess.CalledProcessError as e:
        print e
        print "Error occured while processing i2cset for rail %.2d " % (rail_number + 1)
        return

    print "Voltage margining done"

    return

#
# Dispatches UCD requests
#
def ucd(argv):

    arg_ucd = argv[2:]

    if arg_ucd[0] == "help" or arg_ucd[0] == "h" or len(arg_ucd) < 3:
        error_ucd_usage()
        return

    if arg_ucd[0] == "sh":
        if arg_ucd[2] == "Jbay" or arg_ucd[2] == "jbay" :
            ucd_rail_voltage_jbay()
        else :
            error_ucd_usage()
            return
    elif arg_ucd[0] == "set_margin":
        ucd_voltage_margin(arg_ucd)
	#ucd_ir_voltage_margin(argv)
    elif arg_ucd[0] == "fault":
        ucd_rail_voltage_fault()
    else:
        error_ucd_usage()
        return

    return

def ir_voltage_show_jbay():

    IR_I2C_BUS = "0x1"
    IR_PMBUS_ADDR = {1: "0x70", 2: "0x72", 3: "0x75"}
    IR_VOUT_MODE_OP = "0x20"
    IR_READ_VOUT_OP = "0x8b"
    IR_READ_IOUT_OP = "0x8c"
    string ={1: "VDD_CORE", 2: "AVDD", 3: "QSFP"}

    for i in range(1, 4):

        try:
            # i2cget -f -y 1 0x70 0x8b w
            get_cmd = "i2cget"
            exponent = subprocess.check_output([get_cmd, "-f", "-y", IR_I2C_BUS,
                                     IR_PMBUS_ADDR.get(i), IR_VOUT_MODE_OP, "w"])
        except subprocess.CalledProcessError as e:
            print e
            print "Error occured while processing VOUT_MODE for IR "
            continue

        try:
            # i2cget -f -y 1 0x70 0x8b w
            get_cmd = "i2cget"
            mantissa = subprocess.check_output([get_cmd, "-f", "-y", IR_I2C_BUS,
                                         IR_PMBUS_ADDR.get(i), IR_READ_VOUT_OP, "w"])
        except subprocess.CalledProcessError as e:
            print e
            print "Error occured while processing i2cget for IR "
            continue

        # 2 ^ exponent
        # exponent is 5 bit signed value. Thus calculating first exponent.
        exp = int(exponent, 16) | ~0x1f
        exp = ~exp + 1
        div = 1 << exp

        mantissa = int(mantissa, 16)

        v = (float(mantissa)/float(div))

        # As referred by hardware spec QSFP voltage need to be * 2
        if i == 3:
            v = v * 2

        # find current
        try:
            # i2cget -f -y 1 0x70 0x8c w
            get_cmd = "i2cget"
            mantissa = subprocess.check_output([get_cmd, "-f", "-y", IR_I2C_BUS,
                                         IR_PMBUS_ADDR.get(i), IR_READ_IOUT_OP, "w"])
        except subprocess.CalledProcessError as e:
            print e
            print "Error occured while processing i2cget for IR "
            continue

        m = int(mantissa, 16) & 0x07ff

        # 2 ^ exponent
        # exponent is 5 bit signed value. Thus calculating first exponent.
        exp = int(mantissa, 16) & 0xf800
        exp = exp >> 11
        exp = ~exp + 1
        exp = exp & 0x1f
        div = 1 << exp

        amp = (float(m)/float(div))

        print "IR %-*s       %.3f V    %.3f A      %.3f W" % (15, string.get(i), v, amp, (v * amp))

    return

# IR utility usage
def error_ir_usage():

    print ""
    print "Usage:"
    print "./btools.py --IR sh v <jbay>         => Show IR voltages "
    print "./btools.py --IR set <jbay> <margin>    <voltage rail>  => Set IR voltages margin"
    print "                                           l = low margin       AVDD                   "
    print "                                           h = high margin      VDD_CORE               "
    print "                                           n = normal           QSFP_UPPER  (QSFP for jbay)"
    print "                                                                QSFP_LOWER             "
    print "                                                                RETIMER_VDD  (mav p0c only) "
    print "                                                                RETIMER_VDDA (mav p0c only) "
    print "                                                                REPEATER               "
    print ""
    # Commenting this part as nobody other than Barefoot Hardware team should touch this functionality
    #print "./btools.py --IR set_vdd_core <jbay> <voltage> <= Set IR voltages margin for VDD_CORE"
    #print "                                                       <voltage> must be in range of .65-.95V else discarded"
    #print " eg: ./btools.py --IR set_vdd_core jbay .80 "
    return

def read_vout(rail, I2C_BUS, I2C_ADDR):

    IR_VOUT_MODE_OP = "0x20"
    IR_READ_VOUT_OP = "0x8b"

    try:
      # i2cget -f -y 1 0x70 0x20 w
      get_cmd = "i2cget"
      exponent = subprocess.check_output([get_cmd, "-f", "-y", I2C_BUS,
                                     I2C_ADDR, IR_VOUT_MODE_OP, "w"])
    except subprocess.CalledProcessError as e:
      print e
      print "Error occured while processing VOUT_MODE "

    try:
      # i2cget -f -y 1 0x70 0x8b w
      get_cmd = "i2cget"
      mantissa = subprocess.check_output([get_cmd, "-f", "-y", I2C_BUS,
                                         I2C_ADDR, IR_READ_VOUT_OP, "w"])
    except subprocess.CalledProcessError as e:
      print e
      print "Error occured while processing i2cget "

    # 2 ^ exponent
    # exponent is 5 bit signed value. Thus calculating first exponent.
    exp = int(exponent, 16) | ~0x1f
    exp = ~exp + 1
    div = 1 << exp

    mantissa = int(mantissa, 16)

    v = (float(mantissa)/float(div))

    if not (rail == "VDD_CORE" or rail == "AVDD" or rail == "RETIMER_VDD" or
            rail == "RETIMER_VDDA"):
	v = v * 2

    print ("IR %s       %.3f V" % (rail, v))

    return

def set_ir_voltage(mod, i2c_bus, i2c_addr, margin_cmd, margin_apply, voltage):

  IR_OPERATION = "0x1"

  try:
    # set voltage margin value in register
    set_cmd = "i2cset"
    o = subprocess.check_output([set_cmd, "-f", "-y",
                                i2c_bus, i2c_addr,
                                margin_cmd, voltage, 'w'])

    # execute operation 0x1 with voltage margin AOF
    set_cmd = "i2cset"
    o = subprocess.check_output([set_cmd, "-f", "-y",
                                i2c_bus, i2c_addr,
                                IR_OPERATION, margin_apply])

  except subprocess.CalledProcessError as e:
    print e
    print "Error occured while setting %s voltage" % mod

  read_vout(mod, i2c_bus, i2c_addr)

  return


def fix_jbay_vdd_core_ir_pmbus():

  try:
    # Fix VDD CORE to pmbus
    set_cmd = "i2cset"
    o = subprocess.check_output([set_cmd, "-f", "-y",
                                "1", "0x8", "0x2B", "0x80"])

  except subprocess.CalledProcessError as e:
    print e
    print "Error occured while shifting baxter/IR to PMBUS"

  return

def fix_jbay_avdd_ir_pmbus():

  try:
    # Fix AVDD to pmbus
    set_cmd = "i2cset"
    o = subprocess.check_output([set_cmd, "-f", "-y",
                                "1", "0xA", "0x2B", "0x80"])

  except subprocess.CalledProcessError as e:
    print e
    print "Error occured while shifting baxter/IR to PMBUS"

  return

def ir_voltage_set_jbay(arg_ir):

    IR_I2C_BUS = "0x1"
    IR_PMBUS_ADDR = {1: "0x70", 2: "0x72", 3: "0x75"}
    string_upper = {1: "VDD_CORE", 2: "AVDD", 3: "QSFP"}

    IR_MARGIN_LOW_AOF_OP = "0x98"
    IR_MARGIN_HIGH_AOF_OP = "0xA8"
    IR_MARGIN_OFF = "0x80"
    IR_OPERATION = "0x1"

    IR_VOUT_MARGIN_HIGH = "0x25"
    IR_VOUT_MARGIN_LOW = "0x26"
    IR_VOUT_CMD = "0x21"

    if arg_ir[3] == "AVDD":

      # keep this command for few boards
      #fix_jbay_avdd_ir_pmbus()
      # voltage +3% -3%
      VOLT_MARGIN_HIGH = "0x1DB"
      VOLT_MARGIN_LOW = "0x1BF"
      VOLT_NORMAL = "0x1CE"
      i2c_addr = IR_PMBUS_ADDR.get(2)

      if arg_ir[2] == "l":
        margin_cmd = IR_VOUT_MARGIN_LOW
        margin_apply = IR_MARGIN_LOW_AOF_OP
        voltage = VOLT_MARGIN_LOW

      elif arg_ir[2] == "h":
        margin_cmd = IR_VOUT_MARGIN_HIGH
        margin_apply = IR_MARGIN_HIGH_AOF_OP
        voltage = VOLT_MARGIN_HIGH

      else:
        margin_cmd = IR_VOUT_CMD
        margin_apply = IR_MARGIN_OFF
        voltage = VOLT_NORMAL

      set_ir_voltage(arg_ir[3], IR_I2C_BUS, i2c_addr, margin_cmd, margin_apply, voltage)

    elif arg_ir[3] == "VDD_CORE":

      # keep this command for few boards
      #fix_jbay_vdd_core_ir_pmbus()

      # voltage +2% -2%
      VOLT_MARGIN_HIGH = "0x1B6"
      VOLT_MARGIN_LOW = "0x1A5"
      VOLT_NORMAL = "0x1AE"
      i2c_addr = IR_PMBUS_ADDR.get(1)

      if arg_ir[2] == "l":
        margin_cmd = IR_VOUT_MARGIN_LOW
        margin_apply = IR_MARGIN_LOW_AOF_OP
        voltage = VOLT_MARGIN_LOW

      elif arg_ir[2] == "h":
        margin_cmd = IR_VOUT_MARGIN_HIGH
        margin_apply = IR_MARGIN_HIGH_AOF_OP
        voltage = VOLT_MARGIN_HIGH

      else:
        margin_cmd = IR_VOUT_CMD
        margin_apply = IR_MARGIN_OFF
        voltage = VOLT_NORMAL

      set_ir_voltage(arg_ir[3], IR_I2C_BUS, i2c_addr, margin_cmd, margin_apply, voltage)

    elif arg_ir[3] == "QSFP":

      VOLT_MARGIN_HIGH = "0x361"
      VOLT_MARGIN_LOW = "0x323"
      VOLT_NORMAL =  "0x34D"
      i2c_addr = IR_PMBUS_ADDR.get(3)

      if arg_ir[2] == "l":
        margin_cmd = IR_VOUT_MARGIN_LOW
        margin_apply = IR_MARGIN_LOW_AOF_OP
        voltage = VOLT_MARGIN_LOW

      elif arg_ir[2] == "h":
        margin_cmd = IR_VOUT_MARGIN_HIGH
        margin_apply = IR_MARGIN_HIGH_AOF_OP
        voltage = VOLT_MARGIN_HIGH

      else:
        margin_cmd = IR_VOUT_CMD
        margin_apply = IR_MARGIN_OFF
        voltage = VOLT_NORMAL

      set_ir_voltage(arg_ir[3], IR_I2C_BUS, i2c_addr, margin_cmd, margin_apply, voltage)

    else:
        error_ir_usage()

    return

# Only available for Part SKEW Need by hardware
def ir_set_vdd_core_dynamic_range_jbay(arg_ir):

    VDD_CORE_IR_I2C_BUS = "0x1"
    VDD_CORE_IR_PMBUS_ADDR = "0x70"
    IR_MARGIN_OFF = "0x80"
    IR_VOUT_CMD = "0x21"

    if len(arg_ir) != 3:
        error_ir_usage()
	return

    v = float(arg_ir[2])

    if v < 0.65 or v > 0.95:
	print "Voltage value not in range .65 - .95"
	return
    voltage_scale = {0: "0x14D", 10: "0x152", 20: "0x157", 30: "0x15C", 40: "0x161", 50: "0x166", 60: "0x16c",
                    70: "0x171",  80: "0x176",  85: "0x178",  90: "0x17B", 100: "0x180", 105: "0x182", 110: "0x185", 
                   120: "0x18A", 125: "0x18D", 130: "0x18F", 135: "0x191", 140: "0x194", 150: "0x19A", 155: "0x19C",
                   160: "0x19F", 170: "0x1A4", 175: "0x1A6", 180: "0x1A9", 185: "0x1AB", 190: "0x1AE", 200: "0x1B3",
                   205: "0x1B5", 210: "0x1B8", 220: "0x1BD", 225: "0x1C0", 230: "0x1C3", 235: "0x1C5", 240: "0x1C8",
                   250: "0x1CD", 255: "0x1CF", 260: "0x1D2", 270: "0x1D7", 280: "0x1DC", 290: "0x1E1", 300: "0x1E6"}

    # Convert to mv with -9 exponent
    i = (v * 1000) % 650
    voltage = voltage_scale.get(i)

    if voltage == None:
        error_ir_usage()
	return

    margin_cmd = IR_VOUT_CMD
    margin_apply = IR_MARGIN_OFF
    set_ir_voltage("VDD_CORE", VDD_CORE_IR_I2C_BUS, VDD_CORE_IR_PMBUS_ADDR, margin_cmd, margin_apply, voltage)

    return

def ir(argv):

    arg_ir = argv[2:]

    if arg_ir[0] == "help" or arg_ir[0] == "h" or (len(arg_ir) != 3 and len(arg_ir) != 4):
        error_ir_usage()
        return

    if arg_ir[0] == "sh":
        if arg_ir[2] == "Jbay" or arg_ir[2] == "jbay" :
            ir_voltage_show_jbay()
        else :
            error_ir_usage()
            return
    elif arg_ir[0] == "set":
        if arg_ir[1] == "Jbay" or arg_ir[1] == "jbay" :
            ir_voltage_set_jbay(arg_ir)
        else :
            error_ir_usage()
            return
    elif arg_ir[0] == "set_vdd_core":
        if arg_ir[1] == "Jbay" or arg_ir[1] == "jbay" :
            ir_set_vdd_core_dynamic_range_jbay(arg_ir)
        else :
            error_ir_usage()
            return
    else:
        error_ir_usage()
        return

    return

def ucd_ir_voltage_margin(argv):

    return
#
# Temperature utility usage
#
def error_tmp_usage():

    print " "
    print "Usage:"
    print "./btools.py --TMP <board type> sh           => Show Temp"
    print "                  <board type>      Jbay"
    print "Eg."
    print "./btools.py --TMP Jbay sh        Show Temp sensors values on Jbay"

    return

#
# Lower board temperature sensors. Board exists on Jbay
#
def tmp_lower(board):

    i2c_dev = "/sys/class/i2c-adapter/i2c-3/3-00"

    tmp_sensor = {1: "48/temp1_input",
                  2: "49/temp1_input",
                  3: "4a/temp1_input",
                  4: "4b/temp1_input",
                  5: "4c/temp1_input"}

    cmd = "cat"
    x = 5

    for i in range(1, x):

        path = i2c_dev + tmp_sensor.get(i)
        try:

            output = subprocess.check_output([cmd, path])
            print " TMP SENSOR %.2d                  %.3f C" % (i,
                                                          float(output) / 1000)

        except subprocess.CalledProcessError as e:
            print e
            print "Error occured while reading Temperature sensor %d " % i

    cmd = "i2cget"

    try:
        output = subprocess.check_output([cmd, "-f", "-y", "3", "0x4d",
                                         "0x00", "w"])
        output = int(output, 16)
        t = output & 0xff
        d = output & 0xfff00

        # if d is 0x80 means .0625 * 8(consider only fourth nibble 2 ^ 3)
        if d == 0x8000:
            t = float(t) + .500

        print " TMP SENSOR %.2d                  %.3f C" % (5, t)


        output = subprocess.check_output([cmd, "-f", "-y", "3",
                                         "0x4c", "0x00"])
        output = int(output, 16)
        print " TMP SENSOR MAX LOCAL           %.3f C" % output

        output = subprocess.check_output([cmd, "-f", "-y", "3",
                                         "0x4c", "0x01"])
        output = int(output, 16)
        print " TMP SENSOR MAX Tofino          %.3f C" % (output)

    except subprocess.CalledProcessError as e:
        print e
        print "Error occured while reading Temperature sensor %d " % i

    return

#
# Dispatching temperature sensor requests
#
def tmp(argv):

    if argv[2] == "help" or argv[2] == "h":
        error_tmp_usage()
        return

    if len(argv) != 4:
        error_tmp_usage()
        return

    if argv[3] != "sh":
        error_tmp_usage()
        return

    if argv[2] == "Jbay" or argv[2] =="jbay":
        tmp_lower("Jbay")
    else:
        error_tmp_usage()
        return

    return

def error_usage():
    print "Error in arguments passed. Please look at usage."
    usage()
    return

# Main function parses command line argument and call appropiate tool
def main(argv):

    try:
        opts, args = getopt.getopt(argv[1:], "hP:U:I:T:", ["help", "PSU=", "UCD=", "IR=", "TMP="])

        # No standard identifier.print the usage
        if len(opts) == 0:
            print "Number of invalid arguments %d " % len(args)
            error_usage()
            return

    except getopt.GetoptError:
        error_usage()
        return

    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
        elif opt in ("-P", "--PSU"):
            psu(argv)
        elif opt in ("-U", "--UCD"):
            ucd(argv)
        elif opt in ("-I", "--IR"):
            ir(argv)
        elif opt in ("-T", "--TMP"):
            tmp(argv)
        else:
            error_usage()

    return

if __name__ == '__main__':
    sys.exit(main(sys.argv))
