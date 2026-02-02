![](assets/full-logo.png)

**A replica, near real-time, miniature UK railway station train departure sign based upon a Raspberry Pi Zero and 256x64 SPI OLED display(s). Uses the publicly available [OpenLDBWS API by National Rail Enquiries](https://www.nationalrail.co.uk/).**

## Highlights

- **See local departures**: Display the departures from your local station at home for up-to-date train information.
- **3D-printable cases**: Print your own miniature case to keep everything tidy - both desktop and 'hanging' style available.
- **Dual display support**: Run two displays each showing departures from different platforms from a single Raspberry Pi.
- **Scrolls next X trains**: Loops through a user-defined number of next trains

![](assets/blog-header.jpg)
![](docs/images/completed-unit.jpg)

## How to build

**Check out [the documentation](/docs/01-getting-started.md) for full hardware/software requirements and complete build guide.**

- [Getting Started](/docs/01-getting-started.md)
- [Connecting the display to the Pi](/docs/02-connecting-the-display-to-the-pi.md)
- [Assembling the Case](/docs/03-assembling-the-case.md)
- [Configuration](/docs/04-configuration.md)

## Quick start (balenaCloud)

The recommended deployment path uses balenaCloud for fleet management and OTA updates.

[![balena deploy button](https://balena.io/deploy.svg)](https://dashboard.balena-cloud.com/deploy?repoUrl=https://github.com/Sportsbadger/train-departure-display&defaultDeviceType=raspberry-pi)

1. Create a balenaCloud account.
2. Deploy using the button above.
3. Set the required `apiKey` in the balenaCloud dashboard and optionally adjust other [configuration variables](/docs/04-configuration.md).

## Configuration overview

The only required environment variable is the OpenLDBWS `apiKey`. All other settings are optional and are documented in [Configuration](/docs/04-configuration.md).

## Local development (headless)

You can run the display loop on a development machine without a connected OLED by using `headless=True`.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export apiKey="your-openldbws-api-key"
export departureStation="PAD"
export headless="True"
python src/main.py
```

If you are running on a Raspberry Pi with the OLED attached, omit `headless` to render to the display.

## Credits

This is a fork of [this repo](https://github.com/chrisys/train-departure-display)

"These are the credits from the originator of this work - [Chris Crocker-White ](https://github.com/chrisys) - full credit goes to them. 

A big thanks to [Chris Hutchinson](https://github.com/chrishutchinson/) who originally started this project and inspired me to develop it further. [Blake](https://github.com/ghostseven) made some further improvements and this project was forked from [there](https://github.com/ghostseven/UK-Train-Departure-Display).

The fonts used were painstakingly put together by `DanielHartUK` and can be found on GitHub at https://github.com/DanielHartUK/Dot-Matrix-Typeface - A huge thanks for making that resource available!

Thanks to [@jajasilver](https://github.com/jajsilver/UK-Train-Departure-Display-NRE) and [@MatthewAscough](https://github.com/MatthewAscough/UK-Train-Departure-Display-NRE) for forming the basis of the OpenLDBWS implementation.

Thanks to [@cr3ative](https://github.com/cr3ative) and [@CalamityJames](https://github.com/CalamityJames) for the huge performance improvements and clean up in v0.5.0."
