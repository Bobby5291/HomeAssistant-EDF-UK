# EDF UK Integration for Home Assistant
[![GitHub Release](https://img.shields.io/github/release/Bobby5291/HomeAssistant-EDF-UK.svg?style=for-the-badge)](https://github.com/Bobby5291/HomeAssistant-EDF-UK/releases)
[![GitHub Stars](https://img.shields.io/github/stars/Bobby5291/HomeAssistant-EDF-UK.svg?style=for-the-badge)](https://github.com/Bobby5291/HomeAssistant-EDF-UK/stargazers)
[![GitHub Watchers](https://img.shields.io/github/watchers/Bobby5291/HomeAssistant-EDF-UK.svg?style=for-the-badge)](https://github.com/Bobby5291/HomeAssistant-EDF-UK/watchers)
[![GitHub Forks](https://img.shields.io/github/forks/Bobby5291/HomeAssistant-EDF-UK.svg?style=for-the-badge)](https://github.com/Bobby5291/HomeAssistant-EDF-UK/network)
[![License](https://img.shields.io/github/license/Bobby5291/HomeAssistant-EDF-UK.svg?style=for-the-badge)](LICENSE)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://hacs.xyz/)

A custom Home Assistant integration for retrieving and monitoring EDF UK smart meter energy data directly within Home Assistant.


The aim of this integration is to provide EDF UK users with a seamless way to access electricity usage, tariff information, and energy monitoring within Home Assistant’s Energy Dashboard ecosystem.

---

## Features

- EDF UK account integration
- Smart meter consumption data
- Home Assistant Energy Dashboard support
- Sensor entities for usage and costs
- Ongoing development and improvements

---

## Current Status

### 🚧 Work in Progress

This integration is under active development and is not yet considered production ready.

You may encounter:

- Breaking changes
- Missing features
- API instability
- Limited documentation
- Bugs and incomplete functionality

Feedback, testing, and contributions are welcome.

---

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Navigate to **Integrations**
3. Add this repository as a custom repository:

```text
https://github.com/Bobby5291/HomeAssistant-EDF-UK
```

4. Select category: `Integration`
5. Install the integration
6. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/edf_uk` directory into your Home Assistant `custom_components` folder
2. Restart Home Assistant
3. Add the integration via:

```text
Settings → Devices & Services → Add Integration
```

---

## Configuration

Configuration is currently handled through the Home Assistant UI.

You will need:

- Your EDF UK account credentials
- Access to a supported smart meter account

---

## Credits

A huge thank you to [BottlecapDave](https://github.com/BottlecapDave) and the excellent [Home Assistant Octopus Energy Integration](https://github.com/BottlecapDave/HomeAssistant-OctopusEnergy) project.

This integration is heavily inspired by, and partially based upon, that integration. Their work provided a strong reference for architecture, implementation patterns, and Home Assistant energy ecosystem support.

---

## Disclaimer

This project is unofficial and is not affiliated with or endorsed by:

- EDF Energy UK
- Home Assistant

Use at your own risk.

---

## Contributing

Contributions, bug reports, feature requests, and testing are all appreciated.

Please open an issue or pull request on GitHub.

---

## Development
I plant to continue to add new features as this project is still a work in progress

---

## License

Licensed under the Apache License, Version 2.0.

```text
Copyright 2026 Bobby5291
