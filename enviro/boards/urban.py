import time, math
from machine import Pin, ADC
from breakout_bme280 import BreakoutBME280
from pimoroni_i2c import PimoroniI2C
from phew import logging
from enviro import i2c


# how long to capture the microphone signal for when taking a reading, in milliseconds
MIC_SAMPLE_TIME_MS = 500

sensor_reset_pin = Pin(9, Pin.OUT, value=True)
sensor_enable_pin = Pin(10, Pin.OUT, value=False)
boost_enable_pin = Pin(11, Pin.OUT, value=False)

noise_adc = ADC(0)

def voltage_to_db(voltage):
  return 20 * math.log10(voltage) + 42 # converts voltage to dB. 42 dB accounts for the sensitivity. 

bme280 = BreakoutBME280(i2c, 0x77)

PM1_UGM3                = 2
PM2_5_UGM3              = 3
PM10_UGM3               = 4
PM1_UGM3_ATHMOSPHERIC   = 5
PM2_5_UGM3_ATHMOSPHERIC = 6
PM10_UGM3_ATHMOSPHERIC  = 7
PM0_3_PER_LITRE         = 8
PM0_5_PER_LITRE         = 9
PM1_PER_LITRE           = 10
PM2_5_PER_LITRE         = 11
PM5_PER_LITRE           = 12
PM10_PER_LITRE          = 13

def particulates(particulate_data, measure):
  # bit of a fudge to convert decilitres into litres... who uses decilitre?!
  multiplier = 10 if measure >= PM0_3_PER_LITRE else 1
  return ((particulate_data[measure * 2] << 8) | particulate_data[measure * 2 + 1]) * multiplier

def get_sensor_readings(seconds_since_last, is_usb_power):
  # bme280 returns the register contents immediately and then starts a new reading
  # we want the current reading so do a dummy read to discard register contents first
  bme280.read()
  time.sleep(0.1)
  bme280_data = bme280.read()
  
  logging.debug("  - starting sensor")
  boost_enable_pin.value(True)
  sensor_enable_pin.value(True)
  logging.debug("  - wait 5 seconds for airflow")
  time.sleep(5) # allow airflow to start

  # setup the i2c bus for the particulate sensor
  logging.debug("  - taking pms5003i reading")
  pms_i2c = PimoroniI2C(14, 15, 100000)
  particulate_data = pms_i2c.readfrom_mem(0x12, 0x00, 32)

  sensor_enable_pin.value(False)
  boost_enable_pin.value(False)

  logging.debug("  - taking microphone reading")
  start = time.ticks_ms()
  min_value = 1.65
  max_value = 1.65
  while time.ticks_diff(time.ticks_ms(), start) < MIC_SAMPLE_TIME_MS:
    # value = (noise_adc.read_u16() * 3.3) / 65535
    # commented out previous command to try new command to convert to dB
    mic_voltage = noise_adc.read_u16() * 3.3 / 65535  # Still needed to get voltage
    decibels = voltage_to_db(mic_voltage) # Convert to dB
    min_value = min(min_value, decibels) # Update with dB value
    max_value = max(max_value, decibels)
  
  noise_vpp = max_value - min_value # Vpp is now in dB
  
  # Unit symbols added
  from ucollections import OrderedDict
  return OrderedDict({
    "temperature": f"{round(bme280_data[0], 2)} °C",
    "humidity": f"{round(bme280_data[2], 2)} %",
    "pressure": f"{round(bme280_data[1] / 100.0, 2)} hPa",
    "noise": f"{round(noise_vpp, 3)} dB",
    "pm1": f"{particulates(particulate_data, PM1_UGM3)} µg/m³", 
    "pm2_5": f"{particulates(particulate_data, PM2_5_UGM3)} µg/m³", 
    "pm10": f"{particulates(particulate_data, PM10_UGM3)} µg/m³"
  })
