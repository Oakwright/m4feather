# m4 and generic imports
import board
import neopixel
import busio
import analogio
# Pimoroni EnviroPlusWing
import pimoroni_physical_feather_pins
import simpleio
from lib.pimoroni_envirowing import screen, gas
from lib.pimoroni_envirowing.screen import plotter
from adafruit_bme280 import basic as adafruit_bme280
from pimoroni_circuitpython_ltr559 import Pimoroni_LTR559
from adafruit_bme280.basic import Adafruit_BME280_I2C
# generic display imports
import displayio
import terminalio
from adafruit_display_text import label
# code flow imports
import time
import array
import math
# wifi imports
from digitalio import DigitalInOut
from adafruit_esp32spi import adafruit_esp32spi
from adafruit_esp32spi import adafruit_esp32spi_wifimanager

displayio.release_displays()

# Get wifi details and more from a secrets.py file
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise


def setup_neo_pixel() -> neopixel.NeoPixel:
    m4pixel: neopixel.NeoPixel = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0)
    m4pixel.fill((0, 0, 0))
    return m4pixel


def setup_spi():
    return busio.SPI(board.SCK, board.MOSI, board.MISO)


def setup_wifi(status_light, spi):
    esp32_cs = DigitalInOut(board.D13)
    esp32_ready = DigitalInOut(board.D11)
    esp32_reset = DigitalInOut(board.D12)

    esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)
    wifi_object = adafruit_esp32spi_wifimanager.ESPSPI_WiFiManager(esp, secrets, status_light)
    return wifi_object


pixel: neopixel.NeoPixel = setup_neo_pixel()

spibus = setup_spi()

wifi = setup_wifi(pixel, spibus)


def setup_bme280(i2c_bus: busio.I2C) -> Adafruit_BME280_I2C:
    bme280sensor: Adafruit_BME280_I2C = adafruit_bme280.Adafruit_BME280_I2C(i2c_bus, address=0x76)
    bme280sensor.sea_level_pressure = 1013.25
    return bme280sensor


def setup_i2c_pim() -> busio.I2C:
    i2c_bus: busio.I2C = busio.I2C(board.SCL, board.SDA)
    return i2c_bus


def submit_datapoint(data, feedname):
    try:
        print("Posting data...", end="")
        payload = {"value": data}
        response = wifi.post(
            "https://io.adafruit.com/api/v2/"
            + secrets["aio_username"]
            + "/feeds/"
            + feedname
            + "/data",
            json=payload,
            headers={"X-AIO-KEY": secrets["aio_key"]},
        )
        print(response.json())
        response.close()
        print("OK")
    except OSError as e:
        print("Failed to get data, retrying\n", e)
        wifi.reset()
    response = None


def setup_gas_plotter(displayscreen1):
    # Set up the gas screen plotter
    # the max value is set to 3.3 as its the max voltage the feather can read
    gas_splotter1 = plotter.ScreenPlotter([red, green, blue], max_value=3.3, min_value=0.5, top_space=10, display=displayscreen1)

    # add a colour coded text label for each reading
    gas_splotter1.group.append(label.Label(terminalio.FONT, text="OX: {:.0f}", color=red, x=0, y=5))
    gas_splotter1.group.append(label.Label(terminalio.FONT, text="RED: {:.0f}", color=green, x=50, y=5))
    gas_splotter1.group.append(label.Label(terminalio.FONT, text="NH3: {:.0f}", color=blue, x=110, y=5))
    return gas_splotter1


def process_pim_pulse():

    #  gas_reading = gas.read_all()
    # update the line graph
    # the value plotted on the graph is the voltage drop over each sensor, not the resistance, as it graphs nicer
    oxidizing = gas_reading._OX.value * (gas_reading._OX.reference_voltage / 65535)
    reducing = gas_reading._RED.value * (gas_reading._RED.reference_voltage / 65535)
    nh3 = gas_reading._NH3.value * (gas_reading._NH3.reference_voltage / 65535)



    print(str(oxidizing) + " " + str(reducing) + " " + str(nh3))


PIM_PLUGGED_IN = False
#try:
i2cP: busio.I2C = setup_i2c_pim()
bme280: Adafruit_BME280_I2C = setup_bme280(i2cP)
ltr559 = Pimoroni_LTR559(i2cP)
gas_reading = gas.read_all()
mic: analogio.AnalogIn = analogio.AnalogIn(pimoroni_physical_feather_pins.pin8())
displayscreen = screen.Screen(spi=spibus)
PIM_PLUGGED_IN = True
#except Exception:
#    PIM_PLUGGED_IN = False
#    if 'i2cP' in locals():
#        i2cP.deinit()


# colours for the plotter are defined as rgb values in hex, with 2 bytes for each colour
red = 0xFF0000
green = 0x00FF00
blue = 0x0000FF

pim_interval = 30
last_reading = time.monotonic()

micmin = 65535
micmax = 0
samples = array.array('H', [0] * 160)

if 'displayscreen' in locals():
    splash: displayio.Group = displayio.Group()
    displayscreen.show(splash)
    test_text = "Hello World"
    test_text_area = label.Label(
        terminalio.FONT, text=test_text, color=0xFFFFFF, x=4, y=6
    )
    splash.append(test_text_area)
    gas_splotter = setup_gas_plotter(displayscreen)

last_pim_reading = time.monotonic()



while True:
    if PIM_PLUGGED_IN and last_pim_reading + pim_interval < time.monotonic():
        last_pim_reading = time.monotonic()
        lux = ltr559.get_lux()
        prox = ltr559.get_proximity()

        process_pim_pulse()

        ox = gas_reading._OX.value * (gas_reading._OX.reference_voltage / 65535)
        red = gas_reading._RED.value * (gas_reading._RED.reference_voltage / 65535)
        nh3 = gas_reading._NH3.value * (gas_reading._NH3.reference_voltage / 65535)

        gas_splotter.update(
            ox,
            red,
            nh3,
            draw=False
        )

        # update the labels
        gas_splotter.group[1].text = "OX:{}".format(ox)
        gas_splotter.group[2].text = "RED:{}".format(red)
        gas_splotter.group[3].text = "NH3:{}".format(nh3)

        gas_splotter.draw()

        temp = bme280.temperature
        pres = bme280.pressure
        hum = bme280.humidity
        alt = bme280.altitude
        sample = abs(mic.value - 32768)
        mic_current = mic.value

        if mic_current > micmax:
            micmax = mic.value
        elif mic_current < micmin:
            micmin = mic_current
        mic_range = micmax - micmin
        micdec = simpleio.map_range(mic_current, micmin, micmax, 0, 1)

        pix_brightness = micdec

        # m4neopixel
        pixel.fill((1, 1, 50))
        pixel.brightness = pix_brightness

        # feed = "enviro.sensor1"
        # submit_datapoint(red, feed)

        submit_datapoint(lux, "enviro.lux")
        submit_datapoint(prox, "enviro.prox")
        submit_datapoint(ox, "enviro.ox")
        submit_datapoint(red, "enviro.red")
        submit_datapoint(nh3, "enviro.nh3")
        submit_datapoint(temp, "enviro.temp")
        submit_datapoint(pres, "enviro.pres")
        submit_datapoint(hum, "enviro.hum")
        submit_datapoint(alt, "enviro.alt")
        submit_datapoint(mic_current, "enviro.mic-current")

        time.sleep(0.01)  # a little delay here helps avoid debounce annoyances
        # end loop
        pass
