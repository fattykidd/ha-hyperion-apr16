![Screenshot 1](assets/Wallpaper2.png)
## Home Assistant integration for the AudioControl Hyperion Apr16

[![GitHub Release](https://img.shields.io/github/v/release/Fattykidd/ha-hyperion-apr16?style=flat-square&color=blue)](https://github.com/Fattykidd/ha-hyperion-apr16/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)

This repo provides a [Home
Assistant](https://www.home-assistant.io/) integration for the [Hyperion Apr-16](https://www.avproglobal.com/products/acp-hype-apr-16) Immersive Sound Pre-Amp Processor.


## Installation

### HACS (recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=fattykidd&repository=ha-hyperion-apr16&category=integration)

1. Make sure [HACS](https://hacs.xyz/) is installed in your Home Assistant instance.
2. In Home Assistant, go to **HACS → Integrations → ⋮ → Custom repositories**.
3. Add `https://github.com/fattykidd/ha-hyperion-apr16` as the repository URL, with category **Integration**.
4. Find "Hyperion Apr-16" in HACS and click **Download**.
5. Restart Home Assistant.
6. Go to **Settings → Devices & Services → Add Integration**, search for "Hyperion", and follow the config flow, entering your Apr16's IP address.

### Manual installation (alternative)

Copy the `hyperion_apr16` directory from a downloaded release .zip into the `custom_components` directory under your Home Assistant configuration directory, and restart Home Assistant. Then follow step 6 above to add the integration via the UI.

Input your Apr-16 IP-address with port and after about 10-15 seconds sensors should appear and update.

## Updating

**Via HACS:** HACS will show an update notification when a new version is released; click **Update**, then restart Home Assistant.

**Manual:** Delete the old `hyperion_apr16` directory from `custom components`, copy the new `hyperion_apr16` folder from the updated release .zip into `custom_components`, and restart Home Assistant.

## Screenshots In Action



## Credits

* **[Home Assistant](https://www.home-assistant.io/)** — For providing an incredible, extensible open-source home automation platform.
* **[AudioControl](https://www.audiocontrol.com/)** — For crafting phenomenal home theater processing hardware.
* **The Open-Source Community** — To all the unpaid developers and hobbyists whose passion and dedication make custom hardware integrations possible.
* **Gemini** — For architectural collaboration, troubleshooting, and code structure assistance throughout development.