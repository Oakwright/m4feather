# m4 and generic imports
import board
import neopixel
import busio
import analogio
from digitalio import DigitalInOut
import simpleio
import asyncio
import time
import array
import math
# generic display imports
import displayio
import terminalio
from adafruit_display_text import label
# hid imports
import usb_hid
from adafruit_hid.mouse import Mouse
# wifi imports
from adafruit_esp32spi import adafruit_esp32spi
from adafruit_esp32spi import adafruit_esp32spi_wifimanager
# nunchuk imports
import adafruit_nunchuk
# Pimoroni EnviroPlusWing
from adafruit_bme280 import basic as adafruit_bme280
from pimoroni_circuitpython_ltr559 import Pimoroni_LTR559
from adafruit_bme280.basic import Adafruit_BME280_I2C
from lib.pimoroni_envirowing.screen import plotter
from lib.pimoroni_envirowing import screen, gas
import pimoroni_physical_feather_pins

# clear anything leftover from previous runs
displayio.release_displays()

# Get wifi details and more from a secrets.py file
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise


# m4 feather express specific functions


def setup_neo_pixel() -> neopixel.NeoPixel:
    m4pixel: neopixel.NeoPixel = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0)
    m4pixel.fill((0, 0, 0))
    return m4pixel


def get_voltage(pin):
    return (pin.value * 3.3) / 65536 * 2


# wifi specific functions


def setup_wifi(status_light, spi):
    esp32_cs = DigitalInOut(board.D13)
    esp32_ready = DigitalInOut(board.D11)
    esp32_reset = DigitalInOut(board.D12)

    esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)
    wifi_object = adafruit_esp32spi_wifimanager.ESPSPI_WiFiManager(esp, secrets, status_light)
    return wifi_object


def submit_datapoint(data, feedname):
    try:
        # print("Posting data...", end="")
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
        # print(response.json())
        response.close()
        # print("OK")
    except OSError as e:
        print("Failed to get data, retrying\n", e)
        wifi.reset()
    response = None


# Enviro+ functions


def setup_bme280(i2c_bus: busio.I2C) -> Adafruit_BME280_I2C:

    bme280sensor: Adafruit_BME280_I2C = adafruit_bme280.Adafruit_BME280_I2C(i2c_bus, address=0x76)
    bme280sensor.sea_level_pressure = 1013.25
    return bme280sensor


def setup_gas_plotter(displayscreen1):
    # Set up the gas screen plotter
    # the max value is set to 3.3 as its the max voltage the feather can read
    gas_splotter1 = plotter.ScreenPlotter([green, red, blue], max_value=3.3, min_value=0.5, top_space=10, display=displayscreen1)

    # add a colour coded text label for each reading
    gas_splotter1.group.append(label.Label(terminalio.FONT, text="OX: {:.0f}", color=green, x=0, y=5))
    gas_splotter1.group.append(label.Label(terminalio.FONT, text="RED: {:.0f}", color=red, x=50, y=5))
    gas_splotter1.group.append(label.Label(terminalio.FONT, text="NH3: {:.0f}", color=blue, x=110, y=5))
    return gas_splotter1


# initialize global m4 feather express objects

vbat_voltage = analogio.AnalogIn(board.VOLTAGE_MONITOR)
pixel: neopixel.NeoPixel = setup_neo_pixel()
spibus = busio.SPI(board.SCK, board.MOSI, board.MISO)
I2C_PLUGGED_IN = False
try:
    i2cbus: busio.I2C = busio.I2C(board.SCL, board.SDA)
    I2C_PLUGGED_IN = True
except RuntimeError:
    print("I2C not initialized")
    pass


# figure out what's plugged in

NUNCHUK_PLUGGED_IN = False
PIM_PLUGGED_IN = False
if I2C_PLUGGED_IN:
    while not i2cbus.try_lock():
        pass
    try:
        print(
            "I2C addresses found:",
            [hex(device_address) for device_address in i2cbus.scan()],
        )
        i2c_device_addresses = i2cbus.scan()
        if int('0x52') in i2c_device_addresses:
            print("Found nunchuk")
            NUNCHUK_PLUGGED_IN = True
        else:
            print("no nunchuk found")
        if int('0x23') in i2c_device_addresses and int('0x76') in i2c_device_addresses:
            print("Found Enviro+")
            PIM_PLUGGED_IN = True
        else:
            print("no pimoroni enviro+ found")

    finally:  # unlock the i2c bus when ctrl-c'ing out of the loop
        i2cbus.unlock()


# initialize global wifi object from airlift featherwing
WIFI_PLUGGED_IN = False
try:
    wifi = setup_wifi(pixel, spibus)
    if wifi.esp.status == adafruit_esp32spi.WL_IDLE_STATUS:
        WIFI_PLUGGED_IN = True
except TimeoutError:
    pass

print("I2C Active: " + str(I2C_PLUGGED_IN))
print("Nunchuk Active: " + str(NUNCHUK_PLUGGED_IN))
print("Enviro+ Active: " + str(PIM_PLUGGED_IN))
print("Wifi Active: " + str(WIFI_PLUGGED_IN))


# initialize global wifi objects from pimoroni enviro+ featherwing

if PIM_PLUGGED_IN:
    bme280: Adafruit_BME280_I2C = setup_bme280(i2cbus)
    ltr559 = Pimoroni_LTR559(i2cbus)
    gas_reading = gas.read_all()
    mic: analogio.AnalogIn = analogio.AnalogIn(pimoroni_physical_feather_pins.pin8())
    displayscreen = screen.Screen(spi=spibus)



# colours for the plotter are defined as rgb values in hex, with 2 bytes for each colour
red = 0xFF0000
green = 0x00FF00
blue = 0x0000FF

last_reading = time.monotonic()



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

# initialize global nunchuk object


# main loop

class Interval:
    """Simple class to hold an interval value. Use .value to to read or write."""

    def __init__(self, initial_interval):
        self.value = initial_interval


async def poll_nunchuk():
    no_exception = False
    try:
        nc = adafruit_nunchuk.Nunchuk(i2cbus)
        m = Mouse(usb_hid.devices)
        no_exception = True

        centerX = 120
        centerY = 110

        scaleX = 0.4
        scaleY = 0.5

        cDown = False
        zDown = False

        # This is to allow double-checking (only on left click - and it doesn't really work)
        CHECK_COUNT = 0
    except Exception:
        pass
    while no_exception:
        # x, y = nc.joystick
        # print("joystick = {},{}".format(x, y))
        # ax, ay, az = nc.acceleration
        # print("accceleration ax={}, ay={}, az={}".format(ax, ay, az))
        # print(nc.buttons.C)
        # print(nc.buttons.Z)
        accel = nc.acceleration
        #    print(accel)
        #    x, y = nc.joystick
        #    print((x,y))
        x = accel[0] / 4
        y = accel[1] / 4
        # print((x, y))
        # Eliminate spurious reads
        if x == 255 or y == 255:
            continue
        relX = x - centerX
        relY = y - centerY

        m.move(int(scaleX * relX), int(scaleY * relY), 0)
        buttons = nc.buttons

        c = buttons.C
        z = buttons.Z

        if z and not zDown:
            stillDown = True
            for n in range(CHECK_COUNT):
                if nc.button_Z:
                    stillDown = False
                    break
            if stillDown:
                m.press(Mouse.LEFT_BUTTON)
                zDown = True
        elif not z and zDown:
            stillDown = True
            for n in range(CHECK_COUNT):
                if not nc.button_Z:
                    stillDown = False
                    break
            if stillDown:
                m.release(Mouse.LEFT_BUTTON)
                zDown = False
        if c and not cDown:
            m.press(Mouse.RIGHT_BUTTON)
            cDown = True
        elif not c and cDown:
            m.release(Mouse.RIGHT_BUTTON)
            cDown = False
        await asyncio.sleep(0)


async def poll_lux(interval):
    while PIM_PLUGGED_IN:
        lux = ltr559.get_lux()
        await asyncio.sleep(interval.value / 2)
        submit_datapoint(lux, "enviro.lux")
        await asyncio.sleep(interval.value / 2)


async def poll_prox(interval):
    while PIM_PLUGGED_IN:
        prox = ltr559.get_proximity()
        await asyncio.sleep(interval.value / 2)
        submit_datapoint(prox, "enviro.prox")
        await asyncio.sleep(interval.value / 2)


async def poll_ox(interval):
    while PIM_PLUGGED_IN:
        ox = gas_reading._OX.value * (gas_reading._OX.reference_voltage / 65535)
        await asyncio.sleep(interval.value / 3)
        gas_splotter.group[1].text = "OX:{}".format(ox)
        gas_splotter.update(
            ox,0,0,
            draw=False
        )
        gas_splotter.draw()
        await asyncio.sleep(interval.value / 3)
        submit_datapoint(ox, "enviro.ox")
        await asyncio.sleep(interval.value / 3)


async def poll_red(interval):
    while PIM_PLUGGED_IN:
        reducing = gas_reading._RED.value * (gas_reading._RED.reference_voltage / 65535)
        await asyncio.sleep(interval.value / 3)
        gas_splotter.group[2].text = "RED:{}".format(reducing)
        gas_splotter.update(
            0,reducing,0,
            draw=False
        )
        gas_splotter.draw()
        await asyncio.sleep(interval.value / 3)
        submit_datapoint(reducing, "enviro.red")
        await asyncio.sleep(interval.value / 3)


async def poll_nh3(interval):
    while PIM_PLUGGED_IN:
        nh3 = gas_reading._NH3.value * (gas_reading._NH3.reference_voltage / 65535)
        await asyncio.sleep(interval.value / 3)
        gas_splotter.group[3].text = "NH3:{}".format(nh3)
        gas_splotter.update(
            0,0,nh3,
            draw=False
        )
        gas_splotter.draw()
        await asyncio.sleep(interval.value / 3)
        submit_datapoint(nh3, "enviro.nh3")
        await asyncio.sleep(interval.value / 3)


async def poll_mic(interval):
    micmin = 65535
    micmax = 0
    while PIM_PLUGGED_IN:
        mic_current = mic.value
        if mic_current > micmax:
            micmax = mic.value
        elif mic_current < micmin:
            micmin = mic_current
        micdec = simpleio.map_range(mic_current, micmin, micmax, 0, 1)
        pix_brightness = micdec
        pixel.fill((1, 1, 50))
        pixel.brightness = pix_brightness
        await asyncio.sleep(interval.value / 2)
        submit_datapoint(mic_current, "enviro.mic-current")
        await asyncio.sleep(interval.value / 2)


async def poll_temp(interval):
    while PIM_PLUGGED_IN:
        temperature = bme280.temperature
        await asyncio.sleep(interval.value / 2)
        submit_datapoint(temperature, "enviro.temp")
        await asyncio.sleep(interval.value / 2)


async def poll_pres(interval):
    while PIM_PLUGGED_IN:
        pres = bme280.pressure
        await asyncio.sleep(interval.value / 2)
        submit_datapoint(pres, "enviro.pres")
        await asyncio.sleep(interval.value / 2)


async def poll_hum(interval):
    while PIM_PLUGGED_IN:
        hum = bme280.humidity
        await asyncio.sleep(interval.value / 2)
        submit_datapoint(hum, "enviro.hum")
        await asyncio.sleep(interval.value / 2)


async def poll_alt(interval):
    while PIM_PLUGGED_IN:
        alt = bme280.altitude
        await asyncio.sleep(interval.value / 2)
        submit_datapoint(alt, "enviro.alt")
        await asyncio.sleep(interval.value / 2)


async def main():
    nunchuk_task = asyncio.create_task(poll_nunchuk())
    pim_interval = Interval(30)
    lux_task = asyncio.create_task(poll_lux(pim_interval))
    prox_task = asyncio.create_task(poll_prox(pim_interval))
    ox_task = asyncio.create_task(poll_ox(pim_interval))
    red_task = asyncio.create_task(poll_red(pim_interval))
    nh3_task = asyncio.create_task(poll_nh3(pim_interval))
    mic_task = asyncio.create_task(poll_mic(pim_interval))
    temp_task = asyncio.create_task(poll_temp(pim_interval))
    pres_task = asyncio.create_task(poll_pres(pim_interval))
    hum_task = asyncio.create_task(poll_hum(pim_interval))
    alt_task = asyncio.create_task(poll_alt(pim_interval))
    await asyncio.gather(nunchuk_task, lux_task, prox_task, ox_task, red_task, nh3_task, mic_task, temp_task, pres_task, hum_task, alt_task)

asyncio.run(main())
